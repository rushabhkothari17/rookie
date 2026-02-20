import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { CartProvider } from "@/contexts/CartContext";
import TopNav from "@/components/TopNav";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import VerifyEmail from "@/pages/VerifyEmail";
import Store from "@/pages/Store";
import ProductDetail from "@/pages/ProductDetail";
import Cart from "@/pages/Cart";
import CheckoutSuccess from "@/pages/CheckoutSuccess";
import Portal from "@/pages/Portal";
import Admin from "@/pages/Admin";
import NotFound from "@/pages/NotFound";

const ProtectedRoute = ({
  children,
  requireAdmin = false,
}: {
  children: React.ReactNode;
  requireAdmin?: boolean;
}) => {
  const { user, loading } = useAuth();
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
    return <Navigate to="/login" replace />;
  }
  if (!user.is_verified) {
    return <Navigate to="/verify" replace />;
  }
  if (requireAdmin && !user.is_admin) {
    return <Navigate to="/store" replace />;
  }
  return <>{children}</>;
};

const AuthedLayout = () => (
  <div className="min-h-screen bg-slate-50">
    <TopNav />
    <main className="aa-container py-8" data-testid="authed-layout">
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
            <Route
              path="/"
              element={<Navigate to="/store" replace />}
            />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/verify" element={<VerifyEmail />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AuthedLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/store" element={<Store />} />
              <Route path="/product/:productId" element={<ProductDetail />} />
              <Route path="/cart" element={<Cart />} />
              <Route path="/checkout/success" element={<CheckoutSuccess />} />
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
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-right" />
      </CartProvider>
    </AuthProvider>
  );
}
