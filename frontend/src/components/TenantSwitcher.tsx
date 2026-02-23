import { useState, useEffect } from "react";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Building2, ChevronDown, Eye } from "lucide-react";
import { Badge } from "@/components/ui/badge";

type Tenant = { id: string; name: string; code: string; status: string };

// Global view-as tenant state — persisted across page reloads via sessionStorage
const _SK_ID = "aa_view_as_tenant_id";
const _SK_NAME = "aa_view_as_tenant_name";

let _viewAsTenantId: string | null = sessionStorage.getItem(_SK_ID);
let _viewAsTenantName: string | null = sessionStorage.getItem(_SK_NAME);
let _listeners: Array<() => void> = [];

export function getViewAsTenantId(): string | null {
  return _viewAsTenantId;
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
  _listeners.forEach(fn => fn());
}

/** Returns the X-View-As-Tenant header value if set */
export function getViewAsTenantHeader(): Record<string, string> {
  if (_viewAsTenantId) return { "X-View-As-Tenant": _viewAsTenantId };
  return {};
}

export function TenantSwitcher() {
  const { user } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [currentName, setCurrentName] = useState<string | null>(_viewAsTenantName);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (user?.role !== "platform_admin") return;
    api.get("/admin/tenants").then(res => setTenants(res.data.tenants || [])).catch(() => {});
  }, [user]);

  useEffect(() => {
    const update = () => setCurrentName(_viewAsTenantName);
    _listeners.push(update);
    return () => { _listeners = _listeners.filter(fn => fn !== update); };
  }, []);

  if (user?.role !== "platform_admin") return null;

  const handleSwitch = (tenant: Tenant | null) => {
    setViewAsTenant(tenant?.id ?? null, tenant?.name ?? null);
    setOpen(false);
    // Force refresh of admin data by reloading
    window.location.reload();
  };

  return (
    <div className="relative">
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
        <div className="absolute top-full mt-1 right-0 w-64 bg-white border border-slate-200 rounded-xl shadow-lg z-50 overflow-hidden" data-testid="tenant-switcher-dropdown">
          <div className="p-2 border-b border-slate-100">
            <p className="text-xs text-slate-500 px-2 py-1 font-medium">View admin as tenant</p>
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
            {tenants.filter(t => t.status === "active").map(t => (
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
          </div>
        </div>
      )}
    </div>
  );
}
