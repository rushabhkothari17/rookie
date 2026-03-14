import { Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { LogOut, ShoppingCart, User, ChevronDown, Menu, X } from "lucide-react";
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
import { useState, useEffect } from "react";

export default function TopNav() {
  const { user, logout } = useAuth();
  const { items } = useCart();
  const location = useLocation();
  const ws = useWebsite();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile menu on route change
  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  const storeName = ws.store_name || "Store";
  const logoUrl = ws.logo_url || null;

  const navItems = [
    { to: "/store", label: ws.nav_store_label || "Store", testId: "nav-store", matchPaths: ["/store", "/product"] },
    { to: "/articles", label: ws.nav_articles_label || "Articles", testId: "nav-articles", matchPaths: ["/articles"] },
    ...(ws.workdrive_enabled
      ? [{ to: "/documents", label: ws.nav_documents_label || "Documents", testId: "nav-documents", matchPaths: ["/documents"] }]
      : []),
    ...(((ws.nav_intake_enabled as unknown) !== false && (ws.nav_intake_enabled as unknown) !== "false") ? [{ to: "/intake-form", label: ws.nav_intake_label || "Intake Form", testId: "nav-intake-form", matchPaths: ["/intake-form"] }] : []),
    { to: "/portal", label: ws.nav_portal_label || "Customer Portal", testId: "nav-portal", matchPaths: ["/portal"] },
    ...(user?.is_admin ? [{ to: "/admin", label: "Admin", testId: "nav-admin", matchPaths: ["/admin"] }] : []),
  ];

  const firstInitial = user?.full_name?.trim()?.[0]?.toUpperCase() || "U";

  return (
    <header
      className="sticky top-0 z-40 backdrop-blur-xl"
      data-testid="top-nav"
      style={{
        borderBottom: "1px solid var(--aa-border)",
        backgroundColor: "color-mix(in srgb, var(--aa-card) 92%, transparent)",
        WebkitBackdropFilter: "blur(20px)",
      }}
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

        {/* Desktop Pill Nav Links */}
        <nav className="hidden md:flex items-center gap-0.5 text-sm flex-1 min-w-0 overflow-hidden" data-testid="nav-links">
          {navItems.map((item) => {
            const active = item.matchPaths.some(p => location.pathname.startsWith(p));
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`relative px-3.5 py-1.5 rounded-full text-sm whitespace-nowrap transition-colors duration-150`}
                style={{
                  fontWeight: active ? 600 : 400,
                  color: active ? "var(--aa-text)" : "var(--aa-muted)",
                }}
                data-testid={item.testId}
              >
                {active && (
                  <motion.span
                    layoutId="nav-active-pill"
                    className="absolute inset-0 rounded-full"
                    style={{ backgroundColor: "var(--aa-surface)" }}
                    initial={false}
                    transition={{ type: "spring", stiffness: 500, damping: 35 }}
                  />
                )}
                <span className="relative z-10">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Right side: switchers, cart, user, hamburger */}
        <div className="flex items-center gap-2 shrink-0 ml-auto md:ml-4">
          {user?.full_name?.trim() && (
            <span className="text-sm hidden lg:inline mr-1" style={{ color: "var(--aa-muted)" }} data-testid="nav-welcome">
              Hi, {user.full_name.trim().split(" ")[0]}
            </span>
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

          {/* User Menu — desktop */}
          <div className="hidden md:block">
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
                {!user?.is_admin && user?.role === "customer" && (
                  <DropdownMenuItem asChild data-testid="nav-user-profile" className="rounded-lg cursor-pointer">
                    <Link to="/profile">
                      <User size={13} className="mr-2 text-slate-400" />
                      My Profile
                    </Link>
                  </DropdownMenuItem>
                )}
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

          {/* Hamburger — mobile only */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden h-9 w-9 rounded-full hover:bg-slate-100"
            onClick={() => setMobileOpen(v => !v)}
            data-testid="nav-hamburger"
            aria-label="Open menu"
          >
            {mobileOpen ? <X size={18} className="text-slate-700" /> : <Menu size={18} className="text-slate-700" />}
          </Button>
        </div>
      </div>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden overflow-hidden"
            style={{ borderTop: "1px solid var(--aa-border)", backgroundColor: "var(--aa-card)" }}
            data-testid="nav-mobile-menu"
          >
            <nav className="flex flex-col px-4 py-3 gap-1">
              {navItems.map((item) => {
                const active = item.matchPaths.some(p => location.pathname.startsWith(p));
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`px-4 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                      active
                        ? "text-slate-900 font-semibold"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                    }`}
                    style={active ? { backgroundColor: "color-mix(in srgb, var(--aa-primary) 8%, white)" } : {}}
                    data-testid={`mobile-${item.testId}`}
                  >
                    {item.label}
                  </Link>
                );
              })}
              <div className="mt-2 pt-2 border-t border-slate-100">
                <div className="px-4 py-2">
                  <div className="text-sm font-semibold text-slate-900 truncate">{user?.full_name}</div>
                  <div className="text-xs text-slate-400 truncate">{user?.email}</div>
                </div>
                {!user?.is_admin && user?.role === "customer" && (
                  <Link to="/profile" className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm text-slate-600 hover:bg-slate-50">
                    <User size={14} />
                    My Profile
                  </Link>
                )}
                <button
                  className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm text-red-500 hover:bg-red-50 text-left"
                  onClick={logout}
                >
                  <LogOut size={14} />
                  Logout
                </button>
              </div>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

