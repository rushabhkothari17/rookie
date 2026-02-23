import { useState, useEffect, useRef } from "react";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { User, ChevronDown, Search, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  getViewAsTenantId,
  subscribeToTenantSwitch,
  getViewAsCustomerId,
  getViewAsCustomerEmail,
  setViewAsCustomer,
  subscribeToCustomerSwitch,
} from "@/components/TenantSwitcher";

type Customer = { id: string; user_id: string; company_name: string; email: string; full_name: string };

export function CustomerSwitcher() {
  const { user } = useAuth();
  const [tenantId, setTenantId] = useState<string | null>(getViewAsTenantId);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [currentEmail, setCurrentEmail] = useState<string | null>(getViewAsCustomerEmail);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Track tenant switching — reload customer list
  useEffect(() => {
    const unsub = subscribeToTenantSwitch(() => {
      const tid = getViewAsTenantId();
      setTenantId(tid);
      setCurrentEmail(getViewAsCustomerEmail());
    });
    return unsub;
  }, []);

  // Track customer switching
  useEffect(() => {
    const unsub = subscribeToCustomerSwitch(() => setCurrentEmail(getViewAsCustomerEmail()));
    return unsub;
  }, []);

  // Fetch customers when tenant changes
  useEffect(() => {
    if (!tenantId) { setCustomers([]); return; }
    api.get(`/admin/tenants/${tenantId}/customers`)
      .then(res => setCustomers(res.data.customers || []))
      .catch(() => setCustomers([]));
  }, [tenantId]);

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

  // Only visible to platform admin when viewing a specific tenant
  if (user?.role !== "platform_admin" || !tenantId) return null;

  const filtered = customers.filter(c =>
    !search ||
    c.email?.toLowerCase().includes(search.toLowerCase()) ||
    c.company_name?.toLowerCase().includes(search.toLowerCase()) ||
    c.full_name?.toLowerCase().includes(search.toLowerCase())
  );

  const handleSwitch = (customer: Customer | null) => {
    setViewAsCustomer(customer?.id ?? null, customer?.email ?? null);
    setOpen(false);
    setSearch("");
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    setViewAsCustomer(null, null);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors"
        data-testid="customer-switcher-btn"
      >
        <User className="h-3.5 w-3.5 text-slate-400" />
        <span className="text-slate-700 font-medium">
          {currentEmail ? `Customer: ${currentEmail}` : "All Customers"}
        </span>
        {currentEmail && (
          <>
            <Badge variant="secondary" className="text-xs py-0">switched</Badge>
            <X
              className="h-3 w-3 text-slate-400 hover:text-red-500 transition-colors"
              onClick={handleClear}
              data-testid="customer-switcher-clear"
            />
          </>
        )}
        <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
      </button>

      {open && (
        <div className="absolute top-full mt-1 right-0 w-80 bg-white border border-slate-200 rounded-xl shadow-lg z-50 overflow-hidden" data-testid="customer-switcher-dropdown">
          <div className="p-2 border-b border-slate-100">
            <p className="text-xs text-slate-500 px-2 py-1 font-medium">View as customer</p>
            <div className="relative mt-1">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
              <input
                autoFocus
                type="text"
                placeholder="Search by email…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-slate-50 focus:outline-none focus:ring-1 focus:ring-slate-300"
                data-testid="customer-search-input"
              />
            </div>
          </div>
          <div className="max-h-64 overflow-y-auto p-1">
            <button
              onClick={() => handleSwitch(null)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 hover:bg-slate-50 transition-colors ${!currentEmail ? "bg-slate-100 font-medium" : ""}`}
              data-testid="customer-switch-all"
            >
              <User className="h-4 w-4 text-slate-400" />
              All Customers (Tenant View)
            </button>
            {filtered.map(c => (
              <button
                key={c.id}
                onClick={() => handleSwitch(c)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 hover:bg-slate-50 transition-colors ${currentEmail === c.email ? "bg-slate-100 font-medium" : ""}`}
                data-testid={`customer-switch-${c.id}`}
              >
                <div className="h-7 w-7 rounded-full bg-slate-100 flex items-center justify-center text-xs font-semibold text-slate-600 shrink-0">
                  {(c.full_name || c.email || "?")[0].toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="font-medium text-slate-800 truncate">{c.email}</div>
                  <div className="text-xs text-slate-400 truncate">
                    {c.company_name || c.full_name || "—"}
                  </div>
                </div>
              </button>
            ))}
            {customers.length === 0 && (
              <p className="text-xs text-slate-400 text-center py-4">No customers for this tenant yet</p>
            )}
            {customers.length > 0 && filtered.length === 0 && search && (
              <p className="text-xs text-slate-400 text-center py-4">No customers match "{search}"</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
