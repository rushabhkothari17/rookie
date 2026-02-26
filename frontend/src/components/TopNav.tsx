import { Link, useLocation } from "react-router-dom";
import { LogOut, ShoppingCart, User } from "lucide-react";
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
import { useEffect, useState } from "react";
import api from "@/lib/api";

export default function TopNav() {
  const { user, logout } = useAuth();
  const { items } = useCart();
  const location = useLocation();
  const ws = useWebsite();
  const [showDocuments, setShowDocuments] = useState(false);

  const storeName = ws.store_name || "Store";
  const logoUrl = ws.logo_url || null;

  useEffect(() => {
    api.get("/store/settings").then(r => {
      setShowDocuments(r.data?.settings?.workdrive_enabled === true);
    }).catch(() => setShowDocuments(false));
  }, []);

  const isActive = (path: string) =>
    location.pathname.startsWith(path)
      ? "font-semibold text-slate-900"
      : "text-slate-500 hover:text-slate-800 transition-colors";

  return (
    <header
      className="sticky top-0 z-40 border-b border-slate-200/60 bg-white/80 backdrop-blur"
      data-testid="top-nav"
    >
      <div className="aa-container flex items-center justify-between py-4">
        <div className="flex items-center gap-6">
          <Link
            to="/store"
            className="flex items-center gap-2 text-lg font-semibold tracking-tight text-slate-900"
            data-testid="nav-logo"
          >
            {logoUrl ? (
              <img src={logoUrl} alt={storeName} className="h-8 w-auto object-contain" data-testid="nav-logo-img" />
            ) : (
              storeName
            )}
          </Link>
          <nav className="flex items-center gap-4 text-sm" data-testid="nav-links">
            <Link to="/store" className={isActive("/store")} data-testid="nav-store">
              {ws.nav_store_label || "Store"}
            </Link>
            <Link to="/articles" className={isActive("/articles")} data-testid="nav-articles">
              {ws.nav_articles_label || "Articles"}
            </Link>
            {showDocuments && (
              <Link to="/documents" className={isActive("/documents")} data-testid="nav-documents">
                Documents
              </Link>
            )}
            <Link to="/portal" className={isActive("/portal")} data-testid="nav-portal">
              {ws.nav_portal_label || "Customer Portal"}
            </Link>
            {user?.is_admin && (
              <Link to="/admin" className={isActive("/admin")} data-testid="nav-admin">
                Admin
              </Link>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          {user?.full_name && (
            <span className="text-sm text-slate-500 hidden md:inline" data-testid="nav-welcome">
              Hi, {user.full_name.split(" ")[0]}
            </span>
          )}
          {user?.role === "platform_admin" && (
            <>
              <TenantSwitcher />
              <CustomerSwitcher />
            </>
          )}
          <Link to="/cart" className="relative" data-testid="nav-cart-link">
            <Button variant="ghost" size="icon" data-testid="nav-cart-button">
              <ShoppingCart size={18} />
            </Button>
            {items.length > 0 && (
              <Badge
                className="absolute -top-2 -right-2 text-white"
                style={{ backgroundColor: "var(--aa-primary)" }}
                data-testid="nav-cart-count"
              >
                {items.length}
              </Badge>
            )}
          </Link>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="gap-2 text-slate-600"
                data-testid="nav-user-trigger"
              >
                <User size={16} />
                {user?.full_name?.split(" ")[0] || "Account"}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56" data-testid="nav-user-menu">
              <div className="px-3 py-2" data-testid="nav-user-info">
                <div className="text-sm font-semibold text-slate-900" data-testid="nav-user-name">
                  {user?.full_name}
                </div>
                <div className="text-xs text-slate-500" data-testid="nav-user-email">
                  {user?.email}
                </div>
              </div>
              <DropdownMenuItem asChild data-testid="nav-user-profile">
                <Link to="/profile">My Profile</Link>
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-red-600"
                onClick={logout}
                data-testid="nav-logout-button"
              >
                <LogOut size={14} className="mr-2" />
                Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
