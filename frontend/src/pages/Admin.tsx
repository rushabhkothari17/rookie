import { useEffect, useState } from "react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";

export default function Admin() {
  const [customers, setCustomers] = useState<any[]>([]);
  const [addresses, setAddresses] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [currencyOverride, setCurrencyOverride] = useState({ email: "", currency: "USD" });
  const [selectedProduct, setSelectedProduct] = useState<any>(null);
  const [selectedOrder, setSelectedOrder] = useState<any>(null);
  const [calendarDate, setCalendarDate] = useState<Date | undefined>();
  const [orderFilters, setOrderFilters] = useState({ email: "", product: "", startDate: "", endDate: "" });

  const load = async () => {
    const [custRes, orderRes, subRes, productRes, logRes] = await Promise.all([
      api.get("/admin/customers"),
      api.get("/admin/orders"),
      api.get("/admin/subscriptions"),
      api.get("/products"),
      api.get("/admin/sync-logs"),
    ]);
    setCustomers(custRes.data.customers || []);
    setAddresses(custRes.data.addresses || []);
    setUsers(custRes.data.users || []);
    setOrders(orderRes.data.orders || []);
    setSubscriptions(subRes.data.subscriptions || []);
    setProducts(productRes.data.products || []);
    setLogs(logRes.data.logs || []);
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

  const getCustomerAddress = (customerId: string) => {
    return addresses.find(a => a.customer_id === customerId);
  };

  return (
    <div className="space-y-6" data-testid="admin-page">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Admin control center</h1>
        <p className="text-sm text-slate-500">Manage customers, orders, and catalog content.</p>
      </div>

      <Tabs
        defaultValue="customers"
        className="space-y-4"
        data-testid="admin-tabs"
        onValueChange={handleTabChange}
      >
        <TabsList>
          <TabsTrigger value="customers" data-testid="admin-tab-customers">Customers</TabsTrigger>
          <TabsTrigger value="orders" data-testid="admin-tab-orders">Orders</TabsTrigger>
          <TabsTrigger value="subscriptions" data-testid="admin-tab-subscriptions">Subscriptions</TabsTrigger>
          <TabsTrigger value="catalog" data-testid="admin-tab-catalog">Catalog</TabsTrigger>
          <TabsTrigger value="sync" data-testid="admin-tab-sync">Zoho sync logs</TabsTrigger>
        </TabsList>

        <TabsContent value="customers" className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-900">Currency override</h3>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <Input
                placeholder="Customer email"
                value={currencyOverride.email}
                onChange={(e) => setCurrencyOverride({ ...currencyOverride, email: e.target.value })}
                data-testid="admin-currency-email"
              />
              <Input
                placeholder="Currency (USD/CAD)"
                value={currencyOverride.currency}
                onChange={(e) => setCurrencyOverride({ ...currencyOverride, currency: e.target.value })}
                data-testid="admin-currency-value"
              />
              <Button onClick={handleCurrencyOverride} data-testid="admin-currency-submit">
                Override
              </Button>
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
                      <TableCell data-testid={`admin-customer-name-${customer.id}`}>
                        {user?.full_name || customer.company_name}
                      </TableCell>
                      <TableCell data-testid={`admin-customer-email-${customer.id}`}>
                        {user?.email || "—"}
                      </TableCell>
                      <TableCell data-testid={`admin-customer-region-${customer.id}`}>
                        {address?.region || "—"}
                      </TableCell>
                      <TableCell data-testid={`admin-customer-country-${customer.id}`}>
                        {address?.country || "—"}
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={customer.allow_bank_transfer ?? true}
                          onCheckedChange={(checked) => handlePaymentMethodToggle(customer.id, "allow_bank_transfer", checked)}
                          data-testid={`admin-customer-bank-toggle-${customer.id}`}
                        />
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={customer.allow_card_payment ?? false}
                          onCheckedChange={(checked) => handlePaymentMethodToggle(customer.id, "allow_card_payment", checked)}
                          data-testid={`admin-customer-card-toggle-${customer.id}`}
                        />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="orders" className="space-y-4">
          <div className="flex items-center gap-3">
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" data-testid="admin-orders-date">
                  {calendarDate ? calendarDate.toDateString() : "Filter by date"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="p-0" data-testid="admin-orders-calendar">
                <Calendar mode="single" selected={calendarDate} onSelect={setCalendarDate} />
              </PopoverContent>
            </Popover>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600" data-testid="admin-orders-list">
            {orders.map((order) => (
              <div key={order.id} className="flex items-center justify-between border-b border-slate-100 py-2" data-testid={`admin-order-${order.id}`}>
                <div>
                  <div data-testid={`admin-order-number-${order.id}`}>{order.order_number}</div>
                  <div className="text-xs text-slate-400" data-testid={`admin-order-status-${order.id}`}>
                    {order.status}
                  </div>
                </div>
                <Dialog
                  open={selectedOrder?.id === order.id}
                  onOpenChange={(open) => {
                    if (!open) setSelectedOrder(null);
                  }}
                >
                  <DialogTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedOrder(order)}
                      data-testid={`admin-order-edit-${order.id}`}
                    >
                      Update
                    </Button>
                  </DialogTrigger>
                  {selectedOrder && selectedOrder.id === order.id && (
                    <DialogContent data-testid="admin-order-dialog">
                      <DialogHeader>
                        <DialogTitle>Update order</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-3">
                        <Input
                          placeholder="Manual status"
                          value={selectedOrder.manual_status || ""}
                          onChange={(e) => setSelectedOrder({ ...selectedOrder, manual_status: e.target.value })}
                          data-testid="admin-order-status-input"
                        />
                        <Textarea
                          placeholder="Internal note"
                          value={selectedOrder.internal_note || ""}
                          onChange={(e) => setSelectedOrder({ ...selectedOrder, internal_note: e.target.value })}
                          data-testid="admin-order-note-input"
                        />
                        <Button onClick={handleOrderSave} data-testid="admin-order-save">
                          Save update
                        </Button>
                      </div>
                    </DialogContent>
                  )}
                </Dialog>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="subscriptions" className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600" data-testid="admin-subscriptions-list">
            {subscriptions.map((sub) => (
              <div key={sub.id} className="flex justify-between border-b border-slate-100 py-2" data-testid={`admin-subscription-${sub.id}`}>
                <span data-testid={`admin-subscription-name-${sub.id}`}>{sub.plan_name}</span>
                <span data-testid={`admin-subscription-status-${sub.id}`}>{sub.status}</span>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="catalog" className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="admin-catalog-list">
            {products.map((product) => (
              <div key={product.id} className="flex items-center justify-between border-b border-slate-100 py-2">
                <div>
                  <div className="text-sm font-semibold text-slate-900">{product.name}</div>
                  <div className="text-xs text-slate-500">{product.sku}</div>
                </div>
                <Dialog
                  open={selectedProduct?.id === product.id}
                  onOpenChange={(open) => {
                    if (!open) setSelectedProduct(null);
                  }}
                >
                  <DialogTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedProduct(product)}
                      data-testid={`admin-edit-${product.id}`}
                    >
                      Edit
                    </Button>
                  </DialogTrigger>
                  {selectedProduct && selectedProduct.id === product.id && (
                    <DialogContent data-testid="admin-edit-dialog">
                      <DialogHeader>
                        <DialogTitle>Edit product</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-3">
                        <Input
                          value={selectedProduct.name}
                          onChange={(e) => setSelectedProduct({ ...selectedProduct, name: e.target.value })}
                          data-testid="admin-product-name"
                        />
                        <Input
                          value={selectedProduct.tagline}
                          onChange={(e) => setSelectedProduct({ ...selectedProduct, tagline: e.target.value })}
                          data-testid="admin-product-tagline"
                        />
                        <Textarea
                          value={selectedProduct.description_long}
                          onChange={(e) => setSelectedProduct({ ...selectedProduct, description_long: e.target.value })}
                          data-testid="admin-product-description"
                        />
                        <Input
                          value={selectedProduct.stripe_price_id || ""}
                          onChange={(e) => setSelectedProduct({ ...selectedProduct, stripe_price_id: e.target.value })}
                          placeholder="Stripe price ID"
                          data-testid="admin-product-stripe"
                        />
                        <Button onClick={handleProductSave} data-testid="admin-product-save">
                          Save changes
                        </Button>
                      </div>
                    </DialogContent>
                  )}
                </Dialog>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="sync" className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600" data-testid="admin-sync-list">
            {logs.map((log) => (
              <div key={log.id} className="flex items-center justify-between border-b border-slate-100 py-2" data-testid={`admin-sync-${log.id}`}>
                <div>
                  <div data-testid={`admin-sync-status-${log.id}`}>{log.entity_type} — {log.status}</div>
                  <div className="text-xs text-slate-400" data-testid={`admin-sync-attempts-${log.id}`}>Attempts: {log.attempts}</div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => api.post(`/admin/sync-logs/${log.id}/retry`, {})}
                  data-testid={`admin-sync-retry-${log.id}`}
                >
                  Retry
                </Button>
              </div>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
