import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";

export default function Portal() {
  const [orders, setOrders] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);
  const [subscriptions, setSubscriptions] = useState<any[]>([]);

  const load = async () => {
    const [ordersRes, subsRes] = await Promise.all([
      api.get("/orders"),
      api.get("/subscriptions"),
    ]);
    setOrders(ordersRes.data.orders || []);
    setItems(ordersRes.data.items || []);
    setSubscriptions(subsRes.data.subscriptions || []);
  };

  useEffect(() => {
    load();
  }, []);

  const orderItems = (orderId: string) =>
    items.filter((item) => item.order_id === orderId);

  return (
    <div className="space-y-10" data-testid="portal-page">
      <div>
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
              <TableHead>Subtotal</TableHead>
              <TableHead>Fee</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Details</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {orders.map((order) => (
              <TableRow key={order.id} data-testid={`portal-order-row-${order.id}`}>
                <TableCell data-testid={`portal-order-number-${order.id}`}>{order.order_number}</TableCell>
                <TableCell data-testid={`portal-order-date-${order.id}`}>{order.created_at?.slice(0, 10)}</TableCell>
                <TableCell data-testid={`portal-order-subtotal-${order.id}`}>${order.subtotal.toFixed(2)}</TableCell>
                <TableCell data-testid={`portal-order-fee-${order.id}`}>${order.fee.toFixed(2)}</TableCell>
                <TableCell data-testid={`portal-order-total-${order.id}`}>${order.total.toFixed(2)}</TableCell>
                <TableCell data-testid={`portal-order-status-${order.id}`}>{order.status}</TableCell>
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
                            {item.product_id} — ${item.line_total.toFixed(2)}
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
              <TableHead>Plan</TableHead>
              <TableHead>Start date</TableHead>
              <TableHead>Renewal date</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Cancellation</TableHead>
              <TableHead>Manage</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {subscriptions.map((sub) => (
              <TableRow key={sub.id} data-testid={`portal-subscription-row-${sub.id}`}>
                <TableCell data-testid={`portal-subscription-plan-${sub.id}`}>{sub.plan_name}</TableCell>
                <TableCell data-testid={`portal-subscription-start-${sub.id}`}>{sub.current_period_start?.slice(0, 10)}</TableCell>
                <TableCell data-testid={`portal-subscription-renewal-${sub.id}`}>{sub.current_period_end?.slice(0, 10)}</TableCell>
                <TableCell data-testid={`portal-subscription-status-${sub.id}`}>{sub.status}</TableCell>
                <TableCell data-testid={`portal-subscription-amount-${sub.id}`}>${(sub.amount || 0).toFixed(2)}</TableCell>
                <TableCell data-testid={`portal-subscription-cancel-date-${sub.id}`}>
                  {sub.cancel_at_period_end ? sub.current_period_end?.slice(0, 10) : "—"}
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => api.post(`/subscriptions/${sub.id}/cancel`, {})}
                    data-testid={`subscription-cancel-${sub.id}`}
                  >
                    Cancel
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
