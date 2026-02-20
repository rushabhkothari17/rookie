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

export default function TopNav() {
  const { user, logout } = useAuth();
  const { items } = useCart();
  const location = useLocation();

  const isActive = (path: string) =>
    location.pathname.startsWith(path) ? "text-slate-900" : "text-slate-500";

  return (
    <header
      className="sticky top-0 z-40 border-b border-slate-200/60 bg-white/80 backdrop-blur"
      data-testid="top-nav"
    >
      <div className="aa-container flex items-center justify-between py-4">
        <div className="flex items-center gap-6">
          <Link
            to="/store"
            className="text-lg font-semibold tracking-tight text-slate-900"
            data-testid="nav-logo"
          >
            Automate Accounts
          </Link>
          <nav className="flex items-center gap-4 text-sm" data-testid="nav-links">
            <Link to="/store" className={isActive("/store")} data-testid="nav-store">
              Store
            </Link>
            <Link to="/portal" className={isActive("/portal")} data-testid="nav-portal">
              Portal
            </Link>
            <Link to="/profile" className={isActive("/profile")} data-testid="nav-profile">
              My Profile
            </Link>
            {user?.is_admin && (
              <Link to="/admin" className={isActive("/admin")} data-testid="nav-admin">
                Admin
              </Link>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <Link to="/cart" className="relative" data-testid="nav-cart-link">
            <Button variant="ghost" size="icon" data-testid="nav-cart-button">
              <ShoppingCart size={18} />
            </Button>
            {items.length > 0 && (
              <Badge
                className="absolute -top-2 -right-2 bg-slate-900 text-white"
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
              <DropdownMenuItem asChild data-testid="nav-user-portal">
                <Link to="/portal">Portal</Link>
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
