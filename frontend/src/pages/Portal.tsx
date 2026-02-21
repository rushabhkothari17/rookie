import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";

export default function Portal() {
  const { user } = useAuth();
  const [orders, setOrders] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);
  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [productMap, setProductMap] = useState<Record<string, any>>({});

  const load = async () => {
    const [ordersRes, subsRes, productsRes] = await Promise.all([
      api.get("/orders"),
      api.get("/subscriptions"),
      api.get("/products"),
    ]);
    setOrders(ordersRes.data.orders || []);
    setItems(ordersRes.data.items || []);
    setSubscriptions(subsRes.data.subscriptions || []);
    const map: Record<string, any> = {};
    (productsRes.data.products || []).forEach((product: any) => {
      map[product.id] = product;
    });
    setProductMap(map);
  };

  useEffect(() => {
    load();
  }, []);

  const orderItems = (orderId: string) =>
    items.filter((item) => item.order_id === orderId);

  const oneTimeOrders = orders.filter(
    (order) => order.type !== "subscription_start",
  );

  return (
    <div className="space-y-10" data-testid="portal-page">
      <div>
        <p className="text-sm text-slate-500" data-testid="portal-welcome">
          Welcome, {user?.full_name || "Customer"}
        </p>
        <h1 className="text-2xl font-semibold text-slate-900">Customer portal</h1>
        <p className="text-sm text-slate-500">Track orders and subscriptions in one place.</p>
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-900">One-time orders</h2>
        <Table data-testid="portal-orders-table">
          <TableHeader>
            <TableRow>
              <TableHead>Order</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Products</TableHead>
              <TableHead>Subtotal</TableHead>
              <TableHead>Fee</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Payment</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Details</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {oneTimeOrders.map((order) => (
              <TableRow key={order.id} data-testid={`portal-order-row-${order.id}`}>
                <TableCell data-testid={`portal-order-number-${order.id}`}>{order.order_number}</TableCell>
                <TableCell data-testid={`portal-order-date-${order.id}`}>{order.created_at?.slice(0, 10)}</TableCell>
                <TableCell data-testid={`portal-order-products-${order.id}`}>
                  {orderItems(order.id).map((item) => productMap[item.product_id]?.name || item.product_id).join(", ") || "—"}
                </TableCell>
                <TableCell data-testid={`portal-order-subtotal-${order.id}`}>${order.subtotal.toFixed(2)}</TableCell>
                <TableCell data-testid={`portal-order-fee-${order.id}`}>${order.fee.toFixed(2)}</TableCell>
                <TableCell data-testid={`portal-order-total-${order.id}`}>${order.total.toFixed(2)}</TableCell>
                <TableCell data-testid={`portal-order-payment-${order.id}`}>
                  {order.payment_method === "bank_transfer" ? "Bank Transfer" : order.payment_method === "card" ? "Card" : "—"}
                </TableCell>
                <TableCell data-testid={`portal-order-status-${order.id}`}>
                  <span className={order.status === "awaiting_bank_transfer" ? "text-amber-600" : ""}>
                    {order.status === "awaiting_bank_transfer" ? "Awaiting Bank Transfer" : order.status}
                  </span>
                </TableCell>
                <TableCell>
                  <Dialog>
                    <DialogTrigger asChild>
                      <Button variant="ghost" size="sm" data-testid={`order-view-${order.id}`}>
                        View
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Order details</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-2 text-sm text-slate-600" data-testid={`order-details-${order.id}`}>
                        {orderItems(order.id).map((item) => (
                          <div key={item.id} data-testid={`order-item-${item.id}`}>
                            {productMap[item.product_id]?.name || item.product_id} — ${item.line_total.toFixed(2)}
                          </div>
                        ))}
                      </div>
                    </DialogContent>
                  </Dialog>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-900">Subscriptions</h2>
        <Table data-testid="portal-subscriptions-table">
          <TableHeader>
            <TableRow>
              <TableHead>Sub ID</TableHead>
              <TableHead>Plan</TableHead>
              <TableHead>Start Date</TableHead>
              <TableHead>Renewal Date</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Cancellation</TableHead>
              <TableHead>Manage</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {subscriptions.map((sub) => {
              const startDate = sub.start_date?.slice(0, 10) || sub.current_period_start?.slice(0, 10) || "—";
              const cancelDate = sub.cancel_at_period_end
                ? (sub.current_period_end?.slice(0, 10) || sub.canceled_at?.slice(0, 10) || "—")
                : (sub.canceled_at?.slice(0, 10) || "—");
              // Cancel button only visible after contract end date (or if no contract end date)
              const contractEnd = sub.contract_end_date ? new Date(sub.contract_end_date) : null;
              const contractExpired = !contractEnd || contractEnd < new Date();
              return (
                <TableRow key={sub.id} data-testid={`portal-subscription-row-${sub.id}`}>
                  <TableCell className="font-mono text-xs" data-testid={`portal-subscription-id-${sub.id}`}>{sub.subscription_number || sub.id?.slice(0, 8)}</TableCell>
                  <TableCell data-testid={`portal-subscription-plan-${sub.id}`}>{sub.plan_name}</TableCell>
                  <TableCell data-testid={`portal-subscription-start-${sub.id}`}>{startDate}</TableCell>
                  <TableCell data-testid={`portal-subscription-renewal-${sub.id}`}>{sub.renewal_date?.slice(0, 10) || sub.current_period_end?.slice(0, 10) || "—"}</TableCell>
                  <TableCell data-testid={`portal-subscription-status-${sub.id}`}>
                    {sub.status === "canceled_pending" ? "Cancellation Pending"
                      : sub.status === "active" ? "Active"
                      : sub.status === "offline_manual" ? "Offline / Manual"
                      : sub.status === "cancelled" ? "Cancelled"
                      : sub.status}
                  </TableCell>
                  <TableCell data-testid={`portal-subscription-amount-${sub.id}`}>${(sub.amount || 0).toFixed(2)}</TableCell>
                  <TableCell data-testid={`portal-subscription-cancel-date-${sub.id}`}>{cancelDate}</TableCell>
                  <TableCell>
                    {sub.status !== "cancelled" && sub.status !== "canceled_pending" && contractExpired && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => api.post(`/subscriptions/${sub.id}/cancel`, {})}
                        data-testid={`subscription-cancel-${sub.id}`}
                      >
                        Cancel
                      </Button>
                    )}
                    {sub.status !== "cancelled" && sub.status !== "canceled_pending" && !contractExpired && (
                      <span className="text-xs text-slate-400" data-testid={`subscription-contract-active-${sub.id}`}>
                        Contract active until {sub.contract_end_date?.slice(0, 10)}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
