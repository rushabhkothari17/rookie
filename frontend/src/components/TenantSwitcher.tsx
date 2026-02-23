import { useState, useEffect, useRef } from "react";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Building2, ChevronDown, Eye, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";

type Tenant = { id: string; name: string; code: string; status: string };

// ─── Tenant switcher state ──────────────────────────────────────────────────
const _SK_ID = "aa_view_as_tenant_id";
const _SK_NAME = "aa_view_as_tenant_name";

const _safeGet = (k: string): string | null => {
  try { return typeof window !== "undefined" ? sessionStorage.getItem(k) : null; } catch { return null; }
};
let _viewAsTenantId: string | null = _safeGet(_SK_ID);
let _viewAsTenantName: string | null = _safeGet(_SK_NAME);
let _listeners: Array<() => void> = [];

export function getViewAsTenantId(): string | null { return _viewAsTenantId; }

export function subscribeToTenantSwitch(fn: () => void): () => void {
  _listeners.push(fn);
  return () => { _listeners = _listeners.filter(l => l !== fn); };
}

export function setViewAsTenant(id: string | null, name: string | null) {
  _viewAsTenantId = id;
  _viewAsTenantName = name;
  if (id) {
    sessionStorage.setItem(_SK_ID, id);
    sessionStorage.setItem(_SK_NAME, name ?? "");
  } else {
    sessionStorage.removeItem(_SK_ID);
    sessionStorage.removeItem(_SK_NAME);
  }
  // Clear customer selection when tenant changes
  setViewAsCustomer(null, null, false);
  _listeners.forEach(fn => fn());
}

export function getViewAsTenantHeader(): Record<string, string> {
  const headers: Record<string, string> = {};
  if (_viewAsTenantId) headers["X-View-As-Tenant"] = _viewAsTenantId;
  if (_viewAsCustomerId) headers["X-View-As-Customer"] = _viewAsCustomerId;
  return headers;
}

// ─── Customer switcher state ─────────────────────────────────────────────────
const _CUST_SK_ID = "aa_view_as_customer_id";
const _CUST_SK_EMAIL = "aa_view_as_customer_email";

let _viewAsCustomerId: string | null = _safeGet(_CUST_SK_ID);
let _viewAsCustomerEmail: string | null = _safeGet(_CUST_SK_EMAIL);
let _custListeners: Array<() => void> = [];

export function getViewAsCustomerId(): string | null { return _viewAsCustomerId; }
export function getViewAsCustomerEmail(): string | null { return _viewAsCustomerEmail; }

export function subscribeToCustomerSwitch(fn: () => void): () => void {
  _custListeners.push(fn);
  return () => { _custListeners = _custListeners.filter(l => l !== fn); };
}

export function setViewAsCustomer(id: string | null, email: string | null, notify = true) {
  _viewAsCustomerId = id;
  _viewAsCustomerEmail = email;
  if (id) {
    sessionStorage.setItem(_CUST_SK_ID, id);
    sessionStorage.setItem(_CUST_SK_EMAIL, email ?? "");
  } else {
    sessionStorage.removeItem(_CUST_SK_ID);
    sessionStorage.removeItem(_CUST_SK_EMAIL);
  }
  if (notify) _custListeners.forEach(fn => fn());
}

// ─── TenantSwitcher component ─────────────────────────────────────────────────
export function TenantSwitcher() {
  const { user } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [currentName, setCurrentName] = useState<string | null>(_viewAsTenantName);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (user?.role !== "platform_admin") return;
    api.get("/admin/tenants").then(res => setTenants(res.data.tenants || [])).catch(() => {});
  }, [user]);

  useEffect(() => {
    const update = () => setCurrentName(_viewAsTenantName);
    _listeners.push(update);
    return () => { _listeners = _listeners.filter(fn => fn !== update); };
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  if (user?.role !== "platform_admin") return null;

  const activeTenants = tenants.filter(t => t.status === "active");
  const filtered = search
    ? activeTenants.filter(t =>
        t.name.toLowerCase().includes(search.toLowerCase()) ||
        t.code.toLowerCase().includes(search.toLowerCase())
      )
    : activeTenants.slice(0, 5);
  const hasMore = !search && activeTenants.length > 5;

  const handleSwitch = (tenant: Tenant | null) => {
    setViewAsTenant(tenant?.id ?? null, tenant?.name ?? null);
    setOpen(false);
    setSearch("");
    window.location.reload();
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors"
        data-testid="tenant-switcher-btn"
      >
        <Eye className="h-3.5 w-3.5 text-slate-400" />
        <span className="text-slate-700 font-medium">
          {currentName ? `Viewing: ${currentName}` : "All Tenants"}
        </span>
        {currentName && <Badge variant="secondary" className="text-xs py-0">switched</Badge>}
        <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
      </button>

      {open && (
        <div className="absolute top-full mt-1 right-0 w-72 bg-white border border-slate-200 rounded-xl shadow-lg z-50 overflow-hidden" data-testid="tenant-switcher-dropdown">
          <div className="p-2 border-b border-slate-100">
            <p className="text-xs text-slate-500 px-2 py-1 font-medium">View admin as tenant</p>
            <div className="relative mt-1">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
              <input
                autoFocus
                type="text"
                placeholder="Search by name or code…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-slate-50 focus:outline-none focus:ring-1 focus:ring-slate-300"
                data-testid="tenant-search-input"
              />
            </div>
          </div>
          <div className="max-h-60 overflow-y-auto p-1">
            <button
              onClick={() => handleSwitch(null)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 hover:bg-slate-50 transition-colors ${!currentName ? "bg-slate-100 font-medium" : ""}`}
              data-testid="switch-all-tenants"
            >
              <Building2 className="h-4 w-4 text-slate-400" />
              All Tenants (Platform View)
            </button>
            {filtered.map(t => (
              <button
                key={t.id}
                onClick={() => handleSwitch(t)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 hover:bg-slate-50 transition-colors ${currentName === t.name ? "bg-slate-100 font-medium" : ""}`}
                data-testid={`switch-tenant-${t.code}`}
              >
                <Building2 className="h-4 w-4 text-slate-400" />
                <div>
                  <div className="font-medium text-slate-800">{t.name}</div>
                  <div className="text-xs text-slate-400 font-mono">{t.code}</div>
                </div>
              </button>
            ))}
            {hasMore && (
              <p className="text-[11px] text-slate-400 text-center py-2">
                +{activeTenants.length - 5} more — search to find them
              </p>
            )}
            {search && filtered.length === 0 && (
              <p className="text-xs text-slate-400 text-center py-4">No tenants match your search</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
