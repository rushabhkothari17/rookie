import { ReactNode } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { CartProvider } from "@/contexts/CartContext";
import { WebsiteProvider } from "@/contexts/WebsiteContext";
import TopNav from "@/components/TopNav";
import ErrorBoundary from "@/components/ErrorBoundary";
import { CookieConsent } from "@/components/CookieConsent";
import { PageLoader } from "@/components/PageLoader";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import VerifyEmail from "@/pages/VerifyEmail";
import ForgotPassword from "@/pages/ForgotPassword";
import Store from "@/pages/Store";
import ProductDetail from "@/pages/ProductDetail";
import Cart from "@/pages/Cart";
import CheckoutSuccess from "@/pages/CheckoutSuccess";
import BankTransferSuccess from "@/pages/BankTransferSuccess";
import GoCardlessCallback from "@/pages/GoCardlessCallback";
import Articles from "@/pages/Resources";
import Documents from "@/pages/Documents";
import ArticleView from "@/pages/ResourceView";
import IntakeFormPage from "@/pages/IntakeFormPage";

import Portal from "@/pages/Portal";
import Admin from "@/pages/Admin";
import ProductEditor from "@/pages/ProductEditor";
import InvoiceViewer from "@/pages/InvoiceViewer";

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

import { LimitBanner } from "@/layout/LimitBanner";
import AppFooter from "@/components/AppFooter";

const BaseLayout = () => {
  const location = useLocation();
  return (
    <div className="min-h-screen aa-bg flex flex-col" data-testid="base-layout">
      <TopNav />
      <LimitBanner />
      <main className="aa-container py-10 flex-1" data-testid="base-layout-main">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        >
          <Outlet />
        </motion.div>
      </main>
      <AppFooter />
    </div>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <CartProvider>
        <WebsiteProvider>
        <BrowserRouter>
          <PageLoader />
          <Routes>
            <Route path="/" element={<Navigate to="/store" replace />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/verify" element={<VerifyEmail />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            
            {/* Full-screen Product Editor routes - outside BaseLayout */}
            <Route
              path="/admin/products/new"
              element={
                <ProtectedRoute requireAdmin>
                  <ProductEditor />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/products/:id/edit"
              element={
                <ProtectedRoute requireAdmin>
                  <ProductEditor />
                </ProtectedRoute>
              }
            />
            
            {/* Public product detail — accessible without login so unauthenticated visitors can browse and see dynamic pricing */}
            <Route path="/product/:productId" element={<ProductDetail />} />

            <Route element={<ProtectedRoute><Outlet /></ProtectedRoute>}>
              <Route path="/store" element={<Store />} />
              <Route path="/articles" element={<Articles />} />
              <Route path="/articles/:articleId" element={<ArticleView />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/resources" element={<Articles />} />
              <Route path="/resources/:articleId" element={<ArticleView />} />
              <Route element={<BaseLayout />}>
                <Route path="/cart" element={<ErrorBoundary><Cart /></ErrorBoundary>} />
                <Route path="/checkout/success" element={<CheckoutSuccess />} />
                <Route path="/checkout/bank-transfer" element={<BankTransferSuccess />} />
                <Route path="/gocardless/callback" element={<ErrorBoundary><GoCardlessCallback /></ErrorBoundary>} />
                <Route path="/profile" element={<Profile />} />

                <Route path="/portal" element={<Portal />} />
                <Route path="/intake-form" element={<IntakeFormPage />} />
                <Route path="/invoice/:orderId" element={<InvoiceViewer />} />
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
            <Route path="*" element={<BaseLayout />}>
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
        </WebsiteProvider>
        <Toaster
          richColors
          position="top-right"
          toastOptions={{
            style: {
              borderRadius: "12px",
              border: "1px solid color-mix(in srgb, var(--aa-border) 60%, transparent)",
              backdropFilter: "blur(12px)",
              fontSize: "0.875rem",
            },
            duration: 3500,
          }}
        />
        <CookieConsent />
      </CartProvider>
    </AuthProvider>
  );
}
