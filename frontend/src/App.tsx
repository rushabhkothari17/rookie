import { ReactNode } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from "react-router-dom";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { CartProvider } from "@/contexts/CartContext";
import TopNav from "@/components/TopNav";
import ErrorBoundary from "@/components/ErrorBoundary";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import VerifyEmail from "@/pages/VerifyEmail";
import Store from "@/pages/Store";
import ProductDetail from "@/pages/ProductDetail";
import Cart from "@/pages/Cart";
import CheckoutSuccess from "@/pages/CheckoutSuccess";
import BankTransferSuccess from "@/pages/BankTransferSuccess";
import GoCardlessCallback from "@/pages/GoCardlessCallback";

import Portal from "@/pages/Portal";
import Admin from "@/pages/Admin";

import Profile from "@/pages/Profile";
import NotFound from "@/pages/NotFound";

const ProtectedRoute = ({
  children,
  requireAdmin = false,
}: {
  children: ReactNode;
  requireAdmin?: boolean;
}) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        data-testid="app-loading-state"
      >
        <div className="loading-ring" data-testid="app-loading-spinner" />
      </div>
    );
  }
  if (!user) {
    const redirect = encodeURIComponent(
      `${location.pathname}${location.search}`,
    );
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }
  if (!user.is_verified) {
    return <Navigate to="/verify" replace />;
  }
  if (requireAdmin && !user.is_admin) {
    return <Navigate to="/store" replace />;
  }
  return <>{children}</>;
};

const BaseLayout = () => (
  <div className="min-h-screen aa-bg" data-testid="base-layout">
    <TopNav />
    <main className="aa-container py-10" data-testid="base-layout-main">
      <Outlet />
    </main>
  </div>
);

export default function App() {
  return (
    <AuthProvider>
      <CartProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Navigate to="/store" replace />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/verify" element={<VerifyEmail />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Outlet />
                </ProtectedRoute>
              }
            >
              <Route path="/store" element={<Store />} />
              <Route path="/product/:productId" element={<ProductDetail />} />
              <Route element={<BaseLayout />}>
                <Route path="/cart" element={<Cart />} />
                <Route path="/checkout/success" element={<CheckoutSuccess />} />
                <Route path="/checkout/bank-transfer" element={<BankTransferSuccess />} />
                <Route path="/gocardless/callback" element={<GoCardlessCallback />} />
                <Route path="/profile" element={<Profile />} />

                <Route path="/portal" element={<Portal />} />
                <Route
                  path="/admin"
                  element={
                    <ProtectedRoute requireAdmin>
                      <Admin />
                    </ProtectedRoute>
                  }
                />
              </Route>
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-right" />
      </CartProvider>
    </AuthProvider>
  );
}
