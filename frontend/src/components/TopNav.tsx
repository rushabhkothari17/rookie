import { Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { LogOut, ShoppingCart, User, ChevronDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import { useCart } from "@/contexts/CartContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import { TenantSwitcher } from "@/components/TenantSwitcher";
import { CustomerSwitcher } from "@/components/CustomerSwitcher";

export default function TopNav() {
  const { user, logout } = useAuth();
  const { items } = useCart();
  const location = useLocation();
  const ws = useWebsite();

  const storeName = ws.store_name || "Store";
  const logoUrl = ws.logo_url || null;

  const navItems = [
    { to: "/store", label: ws.nav_store_label || "Store", testId: "nav-store" },
    { to: "/articles", label: ws.nav_articles_label || "Articles", testId: "nav-articles" },
    ...(ws.workdrive_enabled
      ? [{ to: "/documents", label: ws.nav_documents_label || "Documents", testId: "nav-documents" }]
      : []),
    { to: "/portal", label: ws.nav_portal_label || "Customer Portal", testId: "nav-portal" },
    ...(user?.is_admin ? [{ to: "/admin", label: "Admin", testId: "nav-admin" }] : []),
  ];

  const firstInitial = user?.full_name?.trim()?.[0]?.toUpperCase() || "U";

  return (
    <header
      className="sticky top-0 z-40 border-b border-slate-100/80 bg-white/92 backdrop-blur-xl"
      data-testid="top-nav"
      style={{ WebkitBackdropFilter: "blur(20px)" }}
    >
      <div className="aa-container flex items-center justify-between py-3">

        {/* Logo */}
        <Link
          to="/store"
          className="flex items-center gap-2.5 text-[15px] font-bold tracking-tight text-slate-900 shrink-0 mr-6"
          data-testid="nav-logo"
        >
          {logoUrl ? (
            <img src={logoUrl} alt={storeName} className="h-8 w-auto object-contain" data-testid="nav-logo-img" />
          ) : (
            storeName
          )}
        </Link>

        {/* Pill Nav Links */}
        <nav className="flex items-center gap-0.5 text-sm flex-1 min-w-0 overflow-hidden" data-testid="nav-links">
          {navItems.map((item) => {
            const active = location.pathname.startsWith(item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`relative px-3.5 py-1.5 rounded-full text-sm whitespace-nowrap transition-colors duration-150 ${
                  active
                    ? "font-semibold text-slate-900"
                    : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
                }`}
                data-testid={item.testId}
              >
                {active && (
                  <motion.span
                    layoutId="nav-active-pill"
                    className="absolute inset-0 rounded-full bg-slate-100"
                    initial={false}
                    transition={{ type: "spring", stiffness: 500, damping: 35 }}
                  />
                )}
                <span className="relative z-10">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Right side: switchers, cart, user */}
        <div className="flex items-center gap-2 shrink-0 ml-4">
          {user?.full_name?.trim() && (
            <span className="text-sm text-slate-400 hidden lg:inline mr-1" data-testid="nav-welcome">
              Hi, {user.full_name.trim().split(" ")[0]}
            </span>
          )}

          {user?.role === "platform_admin" && (
            <>
              <TenantSwitcher />
              <CustomerSwitcher />
            </>
          )}

          {/* Cart */}
          <Link to="/cart" className="relative" data-testid="nav-cart-link">
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 rounded-full hover:bg-slate-100 no-press"
              data-testid="nav-cart-button"
            >
              <ShoppingCart size={17} className="text-slate-600" />
            </Button>
            <AnimatePresence>
              {items.length > 0 && (
                <motion.div
                  key="cart-badge"
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0, opacity: 0 }}
                  transition={{ type: "spring", stiffness: 600, damping: 28 }}
                  className="absolute -top-1.5 -right-1.5 pointer-events-none"
                >
                  <Badge
                    className="h-[18px] min-w-[18px] px-1 text-[10px] text-white leading-none flex items-center justify-center rounded-full"
                    style={{ backgroundColor: "var(--aa-primary)" }}
                    data-testid="nav-cart-count"
                  >
                    {items.length}
                  </Badge>
                </motion.div>
              )}
            </AnimatePresence>
          </Link>

          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="gap-1.5 text-slate-700 rounded-full px-2 h-9 hover:bg-slate-100 no-press"
                data-testid="nav-user-trigger"
              >
                <div
                  className="h-6 w-6 rounded-full flex items-center justify-center text-[11px] font-bold text-white shrink-0"
                  style={{ backgroundColor: "var(--aa-primary)" }}
                >
                  {firstInitial}
                </div>
                <span className="text-sm font-medium text-slate-700 hidden sm:inline max-w-[100px] truncate">
                  {user?.full_name?.trim().split(" ")[0] || "Account"}
                </span>
                <ChevronDown size={13} className="text-slate-400 shrink-0" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-56 rounded-xl shadow-xl border-slate-100 p-1"
              data-testid="nav-user-menu"
            >
              <div className="px-3 py-2.5 mb-1 border-b border-slate-50" data-testid="nav-user-info">
                <div className="text-sm font-semibold text-slate-900 truncate" data-testid="nav-user-name">
                  {user?.full_name}
                </div>
                <div className="text-xs text-slate-400 truncate" data-testid="nav-user-email">
                  {user?.email}
                </div>
              </div>
              <DropdownMenuItem asChild data-testid="nav-user-profile" className="rounded-lg cursor-pointer">
                <Link to="/profile">
                  <User size={13} className="mr-2 text-slate-400" />
                  My Profile
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-red-500 rounded-lg cursor-pointer focus:text-red-600 focus:bg-red-50"
                onClick={logout}
                data-testid="nav-logout-button"
              >
                <LogOut size={13} className="mr-2" />
                Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
