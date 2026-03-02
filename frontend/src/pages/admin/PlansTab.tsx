import { useState, useEffect, useMemo } from "react";
import React from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Plus, Pencil, Trash2, Power, PowerOff, ScrollText, ChevronDown, ChevronUp, Tag, Zap, Lock, DollarSign, Gift, LayoutList, BarChart2, TrendingDown, ArrowUpRight, Receipt, PlusCircle, MinusCircle } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ColHeader } from "@/components/shared/ColHeader";
import { ISO_CURRENCIES } from "@/lib/constants";
import { useSupportedCurrencies } from "@/hooks/useSupportedCurrencies";

// ─── Plan types ───────────────────────────────────────────────────────────────
type Plan = {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
  is_public: boolean;
  visibility_rules?: VisibilityRule[];
  monthly_price?: number | null;
  currency?: string;
  warning_threshold_pct: number;
  tenant_count?: number;
  is_default?: boolean;
  max_users: number | null;
  max_storage_mb: number | null;
  max_user_roles: number | null;
  max_product_categories: number | null;
  max_product_terms: number | null;
  max_enquiries: number | null;
  max_resources: number | null;
  max_templates: number | null;
  max_email_templates: number | null;
  max_categories: number | null;
  max_forms: number | null;
  max_references: number | null;
  max_orders_per_month: number | null;
  max_customers_per_month: number | null;
  max_subscriptions_per_month: number | null;
  created_at: string;
  updated_at: string;
};

type AuditLog = {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  timestamp?: string;
  created_at?: string;
  details?: Record<string, any>;
};

// ─── One-Time Rate types ──────────────────────────────────────────────────────
type OTPRate = {
  id: string;
  module_key: string;
  label: string;
  price_per_record: number;
  currency: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type OTPModule = { key: string; label: string; description: string };

// ─── Coupon types ─────────────────────────────────────────────────────────────
type Coupon = {
  id: string;
  code: string;
  internal_note?: string;
  discount_type: "percentage" | "fixed_amount";
  discount_value: number;
  expiry_date?: string | null;
  is_single_use: boolean;
  applies_to: "ongoing" | "one_time" | "both";
  applicable_plan_ids?: string[] | null;
  is_one_time_per_org: boolean;
  is_active: boolean;
  usage_count: number;
  created_at: string;
};

// ISO_CURRENCIES imported from @/lib/constants
const LIMIT_FIELDS = [
  { key: "max_users", label: "Users (total)" },
  { key: "max_storage_mb", label: "Storage (MB)" },
  { key: "max_user_roles", label: "User Roles" },
  { key: "max_product_categories", label: "Product Categories" },
  { key: "max_product_terms", label: "Product Terms" },
  { key: "max_enquiries", label: "Enquiries" },
  { key: "max_resources", label: "Resources" },
  { key: "max_templates", label: "Templates" },
  { key: "max_email_templates", label: "Email Templates" },
  { key: "max_categories", label: "Resource Categories" },
  { key: "max_forms", label: "Forms" },
  { key: "max_references", label: "References" },
  { key: "max_orders_per_month", label: "Orders / month" },
  { key: "max_customers_per_month", label: "Customers / month" },
  { key: "max_subscriptions_per_month", label: "Subscriptions / month" },
];

type FormState = Record<string, string>;

type VisibilityRule = { field: string; operator: string; value: string };

const RULE_FIELDS = [
  { value: "partner_code", label: "Partner Code" },
  { value: "country", label: "Country" },
  { value: "base_currency", label: "Base Currency" },
  { value: "name", label: "Org Name" },
];

const RULE_OPERATORS = [
  { value: "equals", label: "equals" },
  { value: "not_equals", label: "not equals" },
  { value: "in", label: "is one of (comma-separated)" },
  { value: "contains", label: "contains" },
];

const defaultForm = (): FormState => ({
  name: "",
  description: "",
  warning_threshold_pct: "80",
  is_public: "false",
  monthly_price: "",
  currency: "GBP",
  ...Object.fromEntries(LIMIT_FIELDS.map(f => [f.key, ""])),
});

function planToForm(plan: Plan): FormState {
  return {
    name: plan.name,
    description: plan.description || "",
    warning_threshold_pct: String(plan.warning_threshold_pct ?? 80),
    is_public: plan.is_public ? "true" : "false",
    monthly_price: plan.monthly_price != null ? String(plan.monthly_price) : "",
    currency: plan.currency || "GBP",
    ...Object.fromEntries(
      LIMIT_FIELDS.map(f => [f.key, plan[f.key as keyof Plan] !== null && plan[f.key as keyof Plan] !== undefined ? String(plan[f.key as keyof Plan]) : ""])
    ),
  };
}

function formToPayload(form: FormState) {
  const payload: Record<string, any> = {
    name: form.name.trim(),
    description: form.description.trim(),
    warning_threshold_pct: parseInt(form.warning_threshold_pct) || 80,
    is_public: form.is_public === "true",
    monthly_price: form.monthly_price !== "" ? parseFloat(form.monthly_price) : null,
    currency: form.currency || "GBP",
  };
  LIMIT_FIELDS.forEach(({ key }) => {
    payload[key] = form[key] !== "" ? parseInt(form[key]) : null;
  });
  return payload;
}

// ─── Plan form modal ──────────────────────────────────────────────────────────
function PlanFormModal({ plan, onClose, onSaved }: { plan: Plan | null; onClose: () => void; onSaved: () => void }) {
  const isEdit = !!plan;
  const isDefault = plan?.is_default;
  const [form, setForm] = useState<FormState>(plan ? planToForm(plan) : defaultForm());
  const [rules, setRules] = useState<VisibilityRule[]>(plan?.visibility_rules || []);
  const [saving, setSaving] = useState(false);
  const { currencies: supportedCurrencies } = useSupportedCurrencies();
  const currencyList = supportedCurrencies.length ? supportedCurrencies : ISO_CURRENCIES;
  const set = (key: string, val: string) => setForm(f => ({ ...f, [key]: val }));

  const addRule = () => setRules(r => [...r, { field: "partner_code", operator: "equals", value: "" }]);
  const removeRule = (i: number) => setRules(r => r.filter((_, idx) => idx !== i));
  const updateRule = (i: number, key: keyof VisibilityRule, val: string) =>
    setRules(r => r.map((rule, idx) => idx === i ? { ...rule, [key]: val } : rule));

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error("Plan name is required"); return; }
    setSaving(true);
    try {
      const payload = { ...formToPayload(form), visibility_rules: rules };
      if (isEdit) {
        const { data } = await api.put(`/admin/plans/${plan.id}`, payload);
        toast.success(`Plan updated — ${data.tenants_propagated} org(s) updated`);
      } else {
        await api.post("/admin/plans", payload);
        toast.success("Plan created");
      }
      onSaved();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {isDefault && <Lock size={14} className="text-amber-500" />}
            {isEdit ? `Edit Plan — ${plan.name}` : "New Plan"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          {isEdit && (
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500">Plan ID (read-only)</label>
              <div className="bg-slate-50 border border-slate-200 rounded px-3 py-2 text-xs font-mono text-slate-500 select-all" data-testid="plan-db-id">{plan.id}</div>
            </div>
          )}
          {isDefault && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700 flex items-center gap-2">
              <Lock size={12} />
              This is the default Free Plan. Some restrictions apply — it cannot be deleted or deactivated.
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Plan Name *</label>
              <Input value={form.name} onChange={e => set("name", e.target.value)} placeholder="e.g. Starter, Growth" data-testid="plan-name-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Warning threshold (%)</label>
              <Input type="number" min={1} max={100} value={form.warning_threshold_pct} onChange={e => set("warning_threshold_pct", e.target.value)} placeholder="80" data-testid="plan-threshold-input" />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Description</label>
            <Textarea rows={2} value={form.description} onChange={e => set("description", e.target.value)} placeholder="Short description…" data-testid="plan-description-input" />
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
            <input id="plan-is-public" type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={form.is_public === "true"} onChange={e => set("is_public", e.target.checked ? "true" : "false")} data-testid="plan-is-public-checkbox" />
            <div>
              <label htmlFor="plan-is-public" className="text-xs font-medium text-slate-700 cursor-pointer">Visible to partners for self-service upgrade</label>
              <p className="text-xs text-slate-400">Partners can see and select this plan from their billing portal.</p>
            </div>
          </div>
            <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Monthly Price</label>
              <Input type="number" min={0} step="0.01" value={form.monthly_price} onChange={e => set("monthly_price", e.target.value)} placeholder="0.00" data-testid="plan-monthly-price-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Currency</label>
              <Select value={form.currency} onValueChange={v => set("currency", v)} data-testid="plan-currency-select">
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{currencyList.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>

          {/* Visibility Rules — only shown when not public */}
          {form.is_public !== "true" && (
            <div className="space-y-3 rounded-lg border border-slate-200 p-3 bg-slate-50">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-700">Visibility Rules</p>
                  <p className="text-xs text-slate-400 mt-0.5">Define which partner orgs can see this plan. Leave empty to hide from all.</p>
                </div>
                <Button type="button" size="sm" variant="outline" onClick={addRule} data-testid="add-visibility-rule-btn">
                  <PlusCircle size={13} className="mr-1.5" /> Add Rule
                </Button>
              </div>
              {rules.length === 0 && (
                <p className="text-xs text-slate-400 italic">No rules — plan is hidden from all partner orgs.</p>
              )}
              {rules.map((rule, i) => (
                <div key={i} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 items-center" data-testid={`visibility-rule-${i}`}>
                  <Select value={rule.field} onValueChange={v => updateRule(i, "field", v)}>
                    <SelectTrigger className="text-xs h-8"><SelectValue /></SelectTrigger>
                    <SelectContent>{RULE_FIELDS.map(f => <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>)}</SelectContent>
                  </Select>
                  <Select value={rule.operator} onValueChange={v => updateRule(i, "operator", v)}>
                    <SelectTrigger className="text-xs h-8"><SelectValue /></SelectTrigger>
                    <SelectContent>{RULE_OPERATORS.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
                  </Select>
                  <input
                    className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs focus:outline-none focus:ring-1 focus:ring-slate-400"
                    placeholder="value"
                    value={rule.value}
                    onChange={e => updateRule(i, "value", e.target.value)}
                    data-testid={`rule-value-${i}`}
                  />
                  <button type="button" onClick={() => removeRule(i)} className="text-slate-400 hover:text-red-500">
                    <MinusCircle size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <p className="text-xs text-slate-400">Leave any limit blank for unlimited.</p>
          <div className="rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
                <tr>
                  <th className="text-left px-3 py-2">Resource</th>
                  <th className="text-left px-3 py-2 w-36">Limit</th>
                </tr>
              </thead>
              <tbody>
                {LIMIT_FIELDS.map(({ key, label }) => (
                  <tr key={key} className="border-t border-slate-100">
                    <td className="px-3 py-2 text-slate-700">{label}</td>
                    <td className="px-3 py-2">
                      <Input type="number" min={0} className="h-7 text-xs w-28" value={form[key] ?? ""} onChange={e => set(key, e.target.value)} placeholder="∞" data-testid={`plan-limit-${key}`} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving} data-testid="save-plan-btn">
            {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Plan"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PlanLogsDrawer({ plan, onClose }: { plan: Plan; onClose: () => void }) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.get(`/admin/plans/${plan.id}/logs`)
      .then(({ data }) => setLogs(data.logs || []))
      .catch(() => toast.error("Failed to load logs"))
      .finally(() => setLoading(false));
  }, [plan.id]);
  const fmt = (iso: string) => { try { return new Date(iso).toLocaleString(); } catch { return iso; } };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><ScrollText className="h-4 w-4" />Logs — {plan.name}</DialogTitle>
        </DialogHeader>
        {loading ? <p className="py-6 text-center text-sm text-slate-400">Loading…</p> :
          logs.length === 0 ? <p className="py-6 text-center text-sm text-slate-400">No logs yet.</p> :
          <div className="space-y-2 mt-2">
            {logs.map(log => (
              <div key={log.id || log.timestamp} className="border border-slate-100 rounded-lg p-3">
                <div className="flex items-center justify-between gap-2">
                  <Badge variant="outline" className="text-[10px]">{log.action}</Badge>
                  <span className="text-xs text-slate-400">{fmt(log.created_at || log.timestamp || "")}</span>
                </div>
                <p className="text-xs text-slate-600 mt-1">by <strong>{log.actor}</strong></p>
                {log.details && Object.keys(log.details).length > 0 && (
                  <pre className="text-[10px] text-slate-500 mt-1 bg-slate-50 p-1.5 rounded overflow-x-auto">{JSON.stringify(log.details, null, 2)}</pre>
                )}
              </div>
            ))}
          </div>}
      </DialogContent>
    </Dialog>
  );
}

// ─── Column Header with Sort + Filter ────────────────────────────────────────
type ColHeaderProps = {
  label: string;
  colKey: string;
  sortCol?: string;
  sortDir?: "asc" | "desc";
  onSort: (col: string, dir: "asc" | "desc") => void;
  onClearSort: () => void;
  filterType: "text" | "number-range" | "status" | "date-range";
  filterValue: any;
  onFilter: (val: any) => void;
  onClearFilter: () => void;
  align?: "left" | "right";
};

function sortLabel(dir: "asc" | "desc", filterType: string) {
  if (filterType === "number-range") return dir === "asc" ? "Low → High" : "High → Low";
  if (filterType === "date-range") return dir === "asc" ? "Oldest first" : "Newest first";
  return dir === "asc" ? "A → Z" : "Z → A";
}

function ColHeader({ label, colKey, sortCol, sortDir, onSort, onClearSort, filterType, filterValue, onFilter, onClearFilter, align = "left" }: ColHeaderProps) {
  const isActive = sortCol === colKey;
  const hasFilter =
    filterType === "text" ? !!filterValue
    : filterType === "status" ? filterValue !== "all"
    : filterType === "number-range" ? !!(filterValue?.min || filterValue?.max)
    : !!(filterValue?.from || filterValue?.to);
  const SortIcon = isActive ? (sortDir === "asc" ? ChevronUp : ChevronDown) : ChevronsUpDown;
  return (
    <th className={`px-4 py-3 text-${align}`}>
      <Popover>
        <PopoverTrigger asChild>
          <button className="flex items-center gap-1 text-xs font-medium uppercase text-slate-500 hover:text-slate-700 group">
            {label}
            <span className="relative inline-flex">
              <SortIcon size={12} className={isActive ? "text-slate-700" : "text-slate-400 group-hover:text-slate-600"} />
              {hasFilter && <span className="absolute -top-1 -right-1 h-1.5 w-1.5 rounded-full bg-blue-500" />}
            </span>
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-52 p-3 space-y-3" align="start" side="bottom">
          <div>
            <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1.5">Sort</p>
            <div className="flex flex-col gap-0.5">
              <button
                onClick={() => isActive && sortDir === "asc" ? onClearSort() : onSort(colKey, "asc")}
                className={`flex items-center gap-2 text-xs px-2 py-1.5 rounded hover:bg-slate-100 ${isActive && sortDir === "asc" ? "bg-slate-100 font-semibold text-slate-800" : "text-slate-600"}`}
              >
                <ChevronUp size={12} /> {sortLabel("asc", filterType)}
              </button>
              <button
                onClick={() => isActive && sortDir === "desc" ? onClearSort() : onSort(colKey, "desc")}
                className={`flex items-center gap-2 text-xs px-2 py-1.5 rounded hover:bg-slate-100 ${isActive && sortDir === "desc" ? "bg-slate-100 font-semibold text-slate-800" : "text-slate-600"}`}
              >
                <ChevronDown size={12} /> {sortLabel("desc", filterType)}
              </button>
            </div>
          </div>
          <hr className="border-slate-100" />
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <p className="text-[10px] font-semibold text-slate-400 uppercase">Filter</p>
              {hasFilter && (
                <button onClick={onClearFilter} className="text-[10px] text-blue-500 hover:underline">Clear</button>
              )}
            </div>
            {filterType === "text" && (
              <Input className="h-7 text-xs" placeholder={`Search…`} value={filterValue || ""} onChange={e => onFilter(e.target.value)} />
            )}
            {filterType === "status" && (
              <div className="space-y-1">
                {[["all", "All"], ["active", "Active"], ["inactive", "Inactive"]].map(([val, lbl]) => (
                  <label key={val} className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" className="h-3.5 w-3.5" checked={filterValue === val} onChange={() => onFilter(val)} />
                    <span className="text-xs text-slate-700">{lbl}</span>
                  </label>
                ))}
              </div>
            )}
            {filterType === "number-range" && (
              <div className="space-y-1.5">
                <Input className="h-7 text-xs" type="number" placeholder="Min" value={filterValue?.min || ""} onChange={e => onFilter({ ...filterValue, min: e.target.value })} />
                <Input className="h-7 text-xs" type="number" placeholder="Max" value={filterValue?.max || ""} onChange={e => onFilter({ ...filterValue, max: e.target.value })} />
              </div>
            )}
            {filterType === "date-range" && (
              <div className="space-y-1.5">
                <div>
                  <p className="text-[10px] text-slate-400 mb-0.5">From</p>
                  <Input className="h-7 text-xs" type="date" value={filterValue?.from || ""} onChange={e => onFilter({ ...filterValue, from: e.target.value })} />
                </div>
                <div>
                  <p className="text-[10px] text-slate-400 mb-0.5">To</p>
                  <Input className="h-7 text-xs" type="date" value={filterValue?.to || ""} onChange={e => onFilter({ ...filterValue, to: e.target.value })} />
                </div>
              </div>
            )}
          </div>
        </PopoverContent>
      </Popover>
    </th>
  );
}

// ─── Plans Section ────────────────────────────────────────────────────────────
function PlansSection() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editPlan, setEditPlan] = useState<Plan | null>(null);
  const [logsPlan, setLogsPlan] = useState<Plan | null>(null);
  const [deletePlan, setDeletePlan] = useState<Plan | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  // ── Sort & filter ──
  const [sort, setSort] = useState<{ col: string; dir: "asc" | "desc" } | null>(null);
  const [filters, setFilters] = useState({
    name: "",
    status: "all" as "all" | "active" | "inactive",
    price: { min: "", max: "" },
    orgs: { min: "", max: "" },
    date: { from: "", to: "" },
  });
  const setF = (key: keyof typeof filters, val: any) => setFilters(f => ({ ...f, [key]: val }));

  const displayPlans = useMemo(() => {
    let result = [...plans];
    if (filters.name) result = result.filter(p => p.name.toLowerCase().includes(filters.name.toLowerCase()) || (p.description || "").toLowerCase().includes(filters.name.toLowerCase()));
    if (filters.status !== "all") result = result.filter(p => filters.status === "active" ? p.is_active : !p.is_active);
    if (filters.price.min) result = result.filter(p => (p.monthly_price ?? 0) >= parseFloat(filters.price.min));
    if (filters.price.max) result = result.filter(p => (p.monthly_price ?? 0) <= parseFloat(filters.price.max));
    if (filters.orgs.min) result = result.filter(p => (p.tenant_count ?? 0) >= parseInt(filters.orgs.min));
    if (filters.orgs.max) result = result.filter(p => (p.tenant_count ?? 0) <= parseInt(filters.orgs.max));
    if (filters.date.from) result = result.filter(p => p.created_at >= filters.date.from);
    if (filters.date.to) result = result.filter(p => p.created_at <= filters.date.to + "T23:59:59");
    if (sort) {
      result.sort((a, b) => {
        let av: any, bv: any;
        if (sort.col === "name") { av = a.name.toLowerCase(); bv = b.name.toLowerCase(); }
        else if (sort.col === "price") { av = a.monthly_price ?? -1; bv = b.monthly_price ?? -1; }
        else if (sort.col === "orgs") { av = a.tenant_count ?? 0; bv = b.tenant_count ?? 0; }
        else if (sort.col === "status") { av = a.is_active ? 1 : 0; bv = b.is_active ? 1 : 0; }
        else if (sort.col === "created") { av = a.created_at; bv = b.created_at; }
        if (av < bv) return sort.dir === "asc" ? -1 : 1;
        if (av > bv) return sort.dir === "asc" ? 1 : -1;
        return 0;
      });
    }
    return result;
  }, [plans, filters, sort]);

  const load = async () => {
    setLoading(true);
    try { const { data } = await api.get("/admin/plans"); setPlans(data.plans || []); }
    catch { toast.error("Failed to load plans"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const handleToggle = async (plan: Plan) => {
    if (plan.is_default) { toast.error("The default Free Plan cannot be deactivated"); return; }
    try { const { data } = await api.patch(`/admin/plans/${plan.id}/status`); toast.success(data.is_active ? "Plan activated" : "Plan deactivated"); load(); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Failed to update status"); }
  };

  const handleDelete = async () => {
    if (!deletePlan) return;
    setDeleteError("");
    try { await api.delete(`/admin/plans/${deletePlan.id}`); toast.success("Plan deleted"); setDeletePlan(null); load(); }
    catch (e: any) { setDeleteError(e.response?.data?.detail || "Failed to delete plan"); }
  };

  const fmt = (iso: string) => { try { return new Date(iso).toLocaleDateString(); } catch { return iso; } };

  if (loading) return <div className="p-4 text-slate-500 text-sm">Loading plans…</div>;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">License Plans</h2>
          <p className="text-sm text-slate-500">Define reusable resource limit templates for partner organisations.</p>
        </div>
        <Button onClick={() => setShowCreate(true)} data-testid="create-plan-btn"><Plus className="h-4 w-4 mr-1" />New Plan</Button>
      </div>

      {plans.length === 0 ? (
        <div className="border border-dashed border-slate-200 rounded-xl p-12 text-center text-slate-400 text-sm">
          No plans yet. Create your first plan to start assigning limits to partner organisations.
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm" data-testid="plans-table">
            <thead className="bg-slate-50">
              <tr>
                <ColHeader label="Plan" colKey="name" sortCol={sort?.col} sortDir={sort?.dir} onSort={(c, d) => setSort({ col: c, dir: d })} onClearSort={() => setSort(null)} filterType="text" filterValue={filters.name} onFilter={v => setF("name", v)} onClearFilter={() => setF("name", "")} />
                <ColHeader label="Price" colKey="price" sortCol={sort?.col} sortDir={sort?.dir} onSort={(c, d) => setSort({ col: c, dir: d })} onClearSort={() => setSort(null)} filterType="number-range" filterValue={filters.price} onFilter={v => setF("price", v)} onClearFilter={() => setF("price", { min: "", max: "" })} />
                <ColHeader label="Orgs" colKey="orgs" sortCol={sort?.col} sortDir={sort?.dir} onSort={(c, d) => setSort({ col: c, dir: d })} onClearSort={() => setSort(null)} filterType="number-range" filterValue={filters.orgs} onFilter={v => setF("orgs", v)} onClearFilter={() => setF("orgs", { min: "", max: "" })} />
                <ColHeader label="Status" colKey="status" sortCol={sort?.col} sortDir={sort?.dir} onSort={(c, d) => setSort({ col: c, dir: d })} onClearSort={() => setSort(null)} filterType="status" filterValue={filters.status} onFilter={v => setF("status", v)} onClearFilter={() => setF("status", "all")} />
                <ColHeader label="Created" colKey="created" sortCol={sort?.col} sortDir={sort?.dir} onSort={(c, d) => setSort({ col: c, dir: d })} onClearSort={() => setSort(null)} filterType="date-range" filterValue={filters.date} onFilter={v => setF("date", v)} onClearFilter={() => setF("date", { from: "", to: "" })} />
                <th className="text-right px-4 py-3 text-xs font-medium uppercase text-slate-500">Actions</th>
              </tr>
            </thead>
            <tbody>
              {displayPlans.map(plan => (
                <React.Fragment key={plan.id}>
                  <tr className="border-t border-slate-100 hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-800">{plan.name}</span>
                        {plan.is_default && <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 text-[10px] font-medium flex items-center gap-0.5"><Lock size={9} />Default</span>}
                      </div>
                      {plan.description && <div className="text-xs text-slate-400 mt-0.5">{plan.description}</div>}
                      {plan.is_public && <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100 text-[10px] mt-1">Public</Badge>}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-700">
                      {plan.monthly_price != null ? `${plan.currency || "GBP"} ${plan.monthly_price.toFixed(2)}/mo` : <span className="text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{plan.tenant_count ?? 0}</td>
                    <td className="px-4 py-3">
                      {plan.is_active
                        ? <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 text-[11px]">Active</Badge>
                        : <Badge className="bg-slate-100 text-slate-500 hover:bg-slate-100 text-[11px]">Inactive</Badge>}
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{fmt(plan.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => setExpanded(expanded === plan.id ? null : plan.id)} data-testid={`expand-plan-${plan.id}`} title="View limits">
                          {expanded === plan.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setLogsPlan(plan)} data-testid={`logs-plan-${plan.id}`} title="Audit logs"><ScrollText className="h-4 w-4" /></Button>
                        <Button size="sm" variant="ghost" onClick={() => setEditPlan(plan)} data-testid={`edit-plan-${plan.id}`} title="Edit"><Pencil className="h-4 w-4" /></Button>
                        <Button size="sm" variant="ghost" onClick={() => handleToggle(plan)} data-testid={`toggle-plan-${plan.id}`} title={plan.is_active ? "Deactivate" : "Activate"} disabled={plan.is_default}>
                          {plan.is_active ? <PowerOff className="h-4 w-4 text-slate-400" /> : <Power className="h-4 w-4 text-emerald-500" />}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => { setDeleteError(""); setDeletePlan(plan); }} data-testid={`delete-plan-${plan.id}`} title="Delete" className="text-red-400 hover:text-red-600" disabled={plan.is_default}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                  {expanded === plan.id && (
                    <tr className="border-t border-slate-100 bg-slate-50">
                      <td colSpan={6} className="px-4 py-3">
                        <div className="grid grid-cols-3 gap-x-6 gap-y-1 text-xs">
                          {LIMIT_FIELDS.map(({ key, label }) => {
                            const val = plan[key as keyof Plan];
                            return (
                              <div key={key} className="flex justify-between">
                                <span className="text-slate-500">{label}</span>
                                <span className="font-medium text-slate-700">{val !== null && val !== undefined ? String(val) : "∞"}</span>
                              </div>
                            );
                          })}
                        </div>
                        <div className="mt-2 text-[10px] font-mono text-slate-400">ID: {plan.id}</div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
              {displayPlans.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-slate-400">
                    No plans match the current filters.{" "}
                    <button className="text-blue-500 hover:underline text-xs" onClick={() => setFilters({ name: "", status: "all", price: { min: "", max: "" }, orgs: { min: "", max: "" }, date: { from: "", to: "" } })}>Clear all filters</button>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && <PlanFormModal plan={null} onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />}
      {editPlan && <PlanFormModal plan={editPlan} onClose={() => setEditPlan(null)} onSaved={() => { setEditPlan(null); load(); }} />}
      {logsPlan && <PlanLogsDrawer plan={logsPlan} onClose={() => setLogsPlan(null)} />}
      {deletePlan && (
        <AlertDialog open onOpenChange={() => setDeletePlan(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete "{deletePlan.name}"?</AlertDialogTitle>
              <AlertDialogDescription>
                This will permanently delete the plan. It cannot be undone.
                {(deletePlan.tenant_count ?? 0) > 0 && <span className="text-red-600 block mt-1">This plan has {deletePlan.tenant_count} org(s) assigned. Deletion will be blocked.</span>}
              </AlertDialogDescription>
            </AlertDialogHeader>
            {deleteError && <p className="text-sm text-red-600 px-1">{deleteError}</p>}
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={handleDelete} data-testid="confirm-delete-plan-btn">Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}

// ─── One-Time Rates Section ───────────────────────────────────────────────────
function OneTimeRatesSection() {
  const [rates, setRates] = useState<OTPRate[]>([]);
  const [modules, setModules] = useState<OTPModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editRate, setEditRate] = useState<OTPRate | null>(null);
  const [deleteRate, setDeleteRate] = useState<OTPRate | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/one-time-plans");
      setRates(data.rates || []);
      setModules(data.modules || []);
    } catch { toast.error("Failed to load rate table"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const usedKeys = new Set(rates.map(r => r.module_key));
  const availableModules = modules.filter(m => !usedKeys.has(m.key));

  const handleDelete = async () => {
    if (!deleteRate) return;
    try { await api.delete(`/admin/one-time-plans/${deleteRate.id}`); toast.success("Rate deleted"); setDeleteRate(null); load(); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  if (loading) return <div className="p-4 text-slate-500 text-sm">Loading rate table…</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">One-Time Limit Rate Table</h2>
          <p className="text-sm text-slate-500">Set the price per unit for each module. Partners buy extra capacity for the current billing cycle only.</p>
        </div>
        {availableModules.length > 0 && (
          <Button onClick={() => setShowCreate(true)} data-testid="create-rate-btn">
            <Plus className="h-4 w-4 mr-1" />Add Rate
          </Button>
        )}
      </div>

      {rates.length === 0 ? (
        <div className="border border-dashed border-slate-200 rounded-xl p-12 text-center text-slate-400 text-sm">
          No rates configured. Add a rate to allow partners to buy extra limits.
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm" data-testid="rates-table">
            <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Module</th>
                <th className="text-left px-4 py-3">Price / Unit</th>
                <th className="text-left px-4 py-3">Currency</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-right px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rates.map(r => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-800">{r.label}</p>
                    <p className="text-xs font-mono text-slate-400">{r.module_key}</p>
                  </td>
                  <td className="px-4 py-3 font-semibold text-slate-900">{r.price_per_record.toFixed(2)}</td>
                  <td className="px-4 py-3 text-slate-600">{r.currency}</td>
                  <td className="px-4 py-3">
                    {r.is_active
                      ? <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 text-[11px]">Active</Badge>
                      : <Badge className="bg-slate-100 text-slate-500 hover:bg-slate-100 text-[11px]">Inactive</Badge>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <Button size="sm" variant="ghost" onClick={() => setEditRate(r)} data-testid={`edit-rate-${r.id}`} title="Edit"><Pencil className="h-4 w-4" /></Button>
                      <Button size="sm" variant="ghost" onClick={() => setDeleteRate(r)} data-testid={`delete-rate-${r.id}`} title="Delete" className="text-red-400 hover:text-red-600"><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && <RateFormDialog modules={availableModules} rate={null} onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />}
      {editRate && <RateFormDialog modules={modules} rate={editRate} onClose={() => setEditRate(null)} onSaved={() => { setEditRate(null); load(); }} />}
      {deleteRate && (
        <AlertDialog open onOpenChange={() => setDeleteRate(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete rate for "{deleteRate.label}"?</AlertDialogTitle>
              <AlertDialogDescription>Partners will no longer be able to purchase extra {deleteRate.label.toLowerCase()}.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={handleDelete} data-testid="confirm-delete-rate-btn">Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}

function RateFormDialog({ modules, rate, onClose, onSaved }: { modules: OTPModule[]; rate: OTPRate | null; onClose: () => void; onSaved: () => void }) {
  const isEdit = !!rate;
  const { currencies: supportedCurrencies } = useSupportedCurrencies();
  const defaultCurrency = supportedCurrencies[0] || "USD";
  const [moduleKey, setModuleKey] = useState(rate?.module_key || "");
  const [price, setPrice] = useState(rate ? String(rate.price_per_record) : "");
  const [currency, setCurrency] = useState(rate?.currency || defaultCurrency);
  const [isActive, setIsActive] = useState(rate?.is_active ?? true);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!moduleKey) { toast.error("Please select a module"); return; }
    if (!price || isNaN(parseFloat(price))) { toast.error("Please enter a valid price"); return; }
    setSaving(true);
    try {
      if (isEdit) {
        await api.put(`/admin/one-time-plans/${rate.id}`, { price_per_record: parseFloat(price), currency, is_active: isActive });
        toast.success("Rate updated");
      } else {
        await api.post("/admin/one-time-plans", { module_key: moduleKey, price_per_record: parseFloat(price), currency, is_active: isActive });
        toast.success("Rate created");
      }
      onSaved();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-sm" data-testid="rate-form-dialog">
        <DialogHeader><DialogTitle>{isEdit ? `Edit Rate — ${rate.label}` : "Add Rate"}</DialogTitle></DialogHeader>
        <div className="space-y-4 py-1">
          {!isEdit && (
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Module *</label>
              <Select value={moduleKey} onValueChange={setModuleKey} data-testid="rate-module-select">
                <SelectTrigger><SelectValue placeholder="Select a module…" /></SelectTrigger>
                <SelectContent>
                  {modules.map(m => <SelectItem key={m.key} value={m.key}>{m.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Price per Unit *</label>
              <Input type="number" min={0} step="0.01" value={price} onChange={e => setPrice(e.target.value)} placeholder="1.00" data-testid="rate-price-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Currency</label>
              <Select value={currency} onValueChange={v => setCurrency(v)} data-testid="rate-currency-select">
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{(supportedCurrencies.length ? supportedCurrencies : ["USD"]).map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
            <input id="rate-active" type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={isActive} onChange={e => setIsActive(e.target.checked)} data-testid="rate-active-switch" />
            <label htmlFor="rate-active" className="text-xs font-medium text-slate-700 cursor-pointer">Active</label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving} data-testid="save-rate-btn">
            {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Rate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Coupons Section ──────────────────────────────────────────────────────────
function CouponsSection() {
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editCoupon, setEditCoupon] = useState<Coupon | null>(null);
  const [deleteCoupon, setDeleteCoupon] = useState<Coupon | null>(null);

  const load = async () => {
    setLoading(true);
    try { const { data } = await api.get("/admin/coupons"); setCoupons(data.coupons || []); }
    catch { toast.error("Failed to load coupons"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const handleDelete = async () => {
    if (!deleteCoupon) return;
    try { await api.delete(`/admin/coupons/${deleteCoupon.id}`); toast.success("Coupon deleted"); setDeleteCoupon(null); load(); }
    catch (e: any) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  const appliesToLabel = (v: string) => ({ ongoing: "Ongoing only", one_time: "One-time only", both: "Both" }[v] || v);
  const fmt = (iso: string) => { try { return new Date(iso).toLocaleDateString(); } catch { return iso; } };

  if (loading) return <div className="p-4 text-slate-500 text-sm">Loading coupons…</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Coupons</h2>
          <p className="text-sm text-slate-500">Manage discount codes partners can apply before upgrading their plan.</p>
        </div>
        <Button onClick={() => setShowCreate(true)} data-testid="create-coupon-btn">
          <Plus className="h-4 w-4 mr-1" />New Coupon
        </Button>
      </div>

      {coupons.length === 0 ? (
        <div className="border border-dashed border-slate-200 rounded-xl p-12 text-center text-slate-400 text-sm">
          No coupons yet. Create your first coupon to offer discounts on plan upgrades.
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm" data-testid="coupons-table">
            <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Code</th>
                <th className="text-left px-4 py-3">Discount</th>
                <th className="text-left px-4 py-3">Applies To</th>
                <th className="text-left px-4 py-3">Expiry</th>
                <th className="text-left px-4 py-3">Flags</th>
                <th className="text-left px-4 py-3">Uses</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-right px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {coupons.map(c => (
                <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <span className="font-mono font-semibold text-slate-800 text-sm">{c.code}</span>
                    {c.internal_note && <p className="text-xs text-slate-400 mt-0.5">{c.internal_note}</p>}
                  </td>
                  <td className="px-4 py-3 font-semibold text-slate-900">
                    {c.discount_type === "percentage" ? `${c.discount_value}%` : `${c.discount_value.toFixed(2)} off`}
                  </td>
                  <td className="px-4 py-3 text-slate-600 text-xs">{appliesToLabel(c.applies_to)}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {c.expiry_date ? fmt(c.expiry_date) : <span className="text-slate-300">No expiry</span>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {c.is_single_use && <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px]">Single-use</span>}
                      {c.is_one_time_per_org && <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px]">Per-org</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{c.usage_count}</td>
                  <td className="px-4 py-3">
                    {c.is_active
                      ? <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 text-[11px]">Active</Badge>
                      : <Badge className="bg-slate-100 text-slate-500 hover:bg-slate-100 text-[11px]">Inactive</Badge>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <Button size="sm" variant="ghost" onClick={() => setEditCoupon(c)} data-testid={`edit-coupon-${c.id}`} title="Edit"><Pencil className="h-4 w-4" /></Button>
                      <Button size="sm" variant="ghost" onClick={() => setDeleteCoupon(c)} data-testid={`delete-coupon-${c.id}`} title="Delete" className="text-red-400 hover:text-red-600"><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && <CouponFormDialog coupon={null} onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />}
      {editCoupon && <CouponFormDialog coupon={editCoupon} onClose={() => setEditCoupon(null)} onSaved={() => { setEditCoupon(null); load(); }} />}
      {deleteCoupon && (
        <AlertDialog open onOpenChange={() => setDeleteCoupon(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete coupon "{deleteCoupon.code}"?</AlertDialogTitle>
              <AlertDialogDescription>This coupon will be permanently deleted and can no longer be used.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={handleDelete} data-testid="confirm-delete-coupon-btn">Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}

function CouponFormDialog({ coupon, onClose, onSaved }: { coupon: Coupon | null; onClose: () => void; onSaved: () => void }) {
  const isEdit = !!coupon;
  const [plans, setPlans] = useState<{ id: string; name: string }[]>([]);
  const [code, setCode] = useState(coupon?.code || "");
  const [note, setNote] = useState(coupon?.internal_note || "");
  const [discountType, setDiscountType] = useState<string>(coupon?.discount_type || "percentage");
  const [discountValue, setDiscountValue] = useState(coupon ? String(coupon.discount_value) : "");
  const [expiryDate, setExpiryDate] = useState(coupon?.expiry_date || "");
  const [isSingleUse, setIsSingleUse] = useState(coupon?.is_single_use ?? false);
  const [appliesTo, setAppliesTo] = useState(coupon?.applies_to || "both");
  const [isOneTimePerOrg, setIsOneTimePerOrg] = useState(coupon?.is_one_time_per_org ?? true);
  const [isActive, setIsActive] = useState(coupon?.is_active ?? true);
  const [restrictPlans, setRestrictPlans] = useState(!!(coupon?.applicable_plan_ids?.length));
  const [selectedPlanIds, setSelectedPlanIds] = useState<string[]>(coupon?.applicable_plan_ids || []);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/admin/plans").then(({ data }) => setPlans((data.plans || []).map((p: any) => ({ id: p.id, name: p.name })))).catch(() => {});
  }, []);

  const togglePlan = (id: string) => setSelectedPlanIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  const handleSave = async () => {
    if (!code.trim()) { toast.error("Coupon code is required"); return; }
    if (!discountValue || isNaN(parseFloat(discountValue))) { toast.error("Enter a valid discount value"); return; }
    const payload: any = {
      code: code.toUpperCase().trim(),
      internal_note: note,
      discount_type: discountType,
      discount_value: parseFloat(discountValue),
      expiry_date: expiryDate || null,
      is_single_use: isSingleUse,
      applies_to: appliesTo,
      is_one_time_per_org: isOneTimePerOrg,
      is_active: isActive,
      applicable_plan_ids: restrictPlans && selectedPlanIds.length > 0 ? selectedPlanIds : null,
    };
    setSaving(true);
    try {
      if (isEdit) {
        await api.put(`/admin/coupons/${coupon.id}`, payload);
        toast.success("Coupon updated");
      } else {
        await api.post("/admin/coupons", payload);
        toast.success("Coupon created");
      }
      onSaved();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="coupon-form-dialog">
        <DialogHeader><DialogTitle>{isEdit ? `Edit Coupon — ${coupon.code}` : "New Coupon"}</DialogTitle></DialogHeader>
        <div className="space-y-4 py-1">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Coupon Code *</label>
              <Input value={code} onChange={e => setCode(e.target.value.toUpperCase())} placeholder="SAVE20" className="font-mono" data-testid="coupon-code-field" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Internal Note</label>
              <Input value={note} onChange={e => setNote(e.target.value)} placeholder="Optional note…" data-testid="coupon-note-field" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Discount Type *</label>
              <Select value={discountType} onValueChange={setDiscountType} data-testid="coupon-discount-type">
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="percentage">Percentage (%)</SelectItem>
                  <SelectItem value="fixed_amount">Fixed Amount</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">
                {discountType === "percentage" ? "Discount %" : "Discount Amount"} *
              </label>
              <Input type="number" min={0} step={discountType === "percentage" ? "1" : "0.01"} value={discountValue} onChange={e => setDiscountValue(e.target.value)} placeholder={discountType === "percentage" ? "20" : "10.00"} data-testid="coupon-discount-value" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Applies To</label>
              <Select value={appliesTo} onValueChange={setAppliesTo} data-testid="coupon-applies-to">
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="both">Both upgrade types</SelectItem>
                  <SelectItem value="ongoing">Ongoing plan only</SelectItem>
                  <SelectItem value="one_time">One-time limits only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Expiry Date</label>
              <Input type="date" value={expiryDate || ""} onChange={e => setExpiryDate(e.target.value)} data-testid="coupon-expiry-date" />
            </div>
          </div>

          <div className="space-y-2 rounded-lg border border-slate-200 p-3">
            <p className="text-xs font-medium text-slate-600 mb-1">Usage Restrictions</p>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={isSingleUse} onChange={e => setIsSingleUse(e.target.checked)} data-testid="coupon-single-use" />
              <span className="text-xs text-slate-700">Single use (global — expires after first redemption)</span>
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={isOneTimePerOrg} onChange={e => setIsOneTimePerOrg(e.target.checked)} data-testid="coupon-per-org" />
              <span className="text-xs text-slate-700">One use per partner organisation</span>
            </label>
          </div>

          {appliesTo !== "one_time" && plans.length > 0 && (
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={restrictPlans} onChange={e => { setRestrictPlans(e.target.checked); if (!e.target.checked) setSelectedPlanIds([]); }} data-testid="coupon-restrict-plans" />
                <span className="text-xs font-medium text-slate-700">Restrict to specific plans</span>
              </label>
              {restrictPlans && (
                <div className="ml-5 space-y-1 max-h-40 overflow-y-auto">
                  {plans.map(p => (
                    <label key={p.id} className="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" className="h-3.5 w-3.5 rounded border-slate-300" checked={selectedPlanIds.includes(p.id)} onChange={() => togglePlan(p.id)} data-testid={`coupon-plan-${p.id}`} />
                      <span className="text-xs text-slate-700">{p.name}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
            <input id="coupon-active" type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={isActive} onChange={e => setIsActive(e.target.checked)} data-testid="coupon-active-switch" />
            <label htmlFor="coupon-active" className="text-xs font-medium text-slate-700 cursor-pointer">Active</label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving} data-testid="save-coupon-btn">
            {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Coupon"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Coupon Usage Report ──────────────────────────────────────────────────────
type UsageRow = {
  order_id: string;
  order_number: string;
  coupon_code: string;
  discount_type: string;
  discount_value: number;
  partner_name: string;
  upgrade_type: string;
  base_amount: number;
  discount_amount: number;
  final_amount: number;
  currency: string;
  status: string;
  used_at: string;
};

type ReportSummary = {
  total_redemptions: number;
  total_discount_given: number;
  total_revenue_from_couponed_orders: number;
  coupons_used: number;
};

function CouponUsageSection() {
  const [rows, setRows] = useState<UsageRow[]>([]);
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterCode, setFilterCode] = useState("");
  const [applied, setApplied] = useState("");

  const load = async (code = "") => {
    setLoading(true);
    try {
      const params = code ? `?coupon_code=${encodeURIComponent(code)}` : "";
      const { data } = await api.get(`/admin/coupon-report${params}`);
      setRows(data.rows || []);
      setSummary(data.summary || null);
    } catch { toast.error("Failed to load usage report"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleFilter = () => { setApplied(filterCode); load(filterCode); };
  const handleClear = () => { setFilterCode(""); setApplied(""); load(""); };

  const fmt = (iso: string) => {
    try { return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }); }
    catch { return iso; }
  };

  const upgradeTypeLabel = (t: string) => ({ ongoing_upgrade: "Ongoing Plan", one_time_upgrade: "One-Time Limits" }[t] || t);
  const discountLabel = (row: UsageRow) =>
    row.discount_type === "percentage" ? `${row.discount_value}%` : row.discount_value ? `${row.currency} ${row.discount_value.toFixed(2)} off` : "";

  return (
    <div className="space-y-6" data-testid="coupon-usage-section">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Coupon Usage Report</h2>
          <p className="text-sm text-slate-500">Every coupon redemption across all partner organisations, with discount breakdown.</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Input
            placeholder="Filter by code…"
            value={filterCode}
            onChange={e => setFilterCode(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === "Enter" && handleFilter()}
            className="h-8 w-36 text-sm font-mono"
            data-testid="report-filter-code"
          />
          <Button size="sm" onClick={handleFilter} data-testid="report-filter-btn" variant="outline">Filter</Button>
          {applied && <Button size="sm" onClick={handleClear} variant="ghost" className="text-slate-400">Clear</Button>}
          <Button size="sm" variant="outline" onClick={() => load(applied)} data-testid="report-refresh-btn">
            <Receipt size={13} className="mr-1" />Refresh
          </Button>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4 text-center" data-testid="summary-redemptions">
            <p className="text-2xl font-bold text-slate-900">{summary.total_redemptions}</p>
            <p className="text-xs text-slate-500 mt-0.5">Total Redemptions</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 text-center" data-testid="summary-coupons-used">
            <p className="text-2xl font-bold text-slate-900">{summary.coupons_used}</p>
            <p className="text-xs text-slate-500 mt-0.5">Unique Coupons Used</p>
          </div>
          <div className="rounded-xl border border-red-100 bg-red-50 p-4 text-center" data-testid="summary-discount-given">
            <p className="text-2xl font-bold text-red-700">
              -{summary.total_discount_given > 0 ? summary.total_discount_given.toFixed(2) : "0.00"}
            </p>
            <p className="text-xs text-red-500 mt-0.5">Total Discount Given</p>
          </div>
          <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-4 text-center" data-testid="summary-revenue">
            <p className="text-2xl font-bold text-emerald-700">
              {summary.total_revenue_from_couponed_orders > 0 ? summary.total_revenue_from_couponed_orders.toFixed(2) : "0.00"}
            </p>
            <p className="text-xs text-emerald-600 mt-0.5">Revenue (Couponed Orders)</p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-sm text-slate-400">Loading report…</div>
      ) : rows.length === 0 ? (
        <div className="border border-dashed border-slate-200 rounded-xl p-12 text-center" data-testid="no-usage-rows">
          <BarChart2 size={28} className="text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-400">No coupon redemptions found{applied ? ` for code "${applied}"` : ""}.</p>
          <p className="text-xs text-slate-400 mt-1">Usage will appear here once partners apply coupons during checkout.</p>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 overflow-hidden" data-testid="usage-report-table">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-left px-4 py-3">Partner</th>
                <th className="text-left px-4 py-3">Coupon</th>
                <th className="text-left px-4 py-3">Upgrade Type</th>
                <th className="text-right px-4 py-3">Original</th>
                <th className="text-right px-4 py-3">Discount</th>
                <th className="text-right px-4 py-3">Paid</th>
                <th className="text-left px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={row.order_id || i} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{fmt(row.used_at)}</td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-800">{row.partner_name || "—"}</p>
                    {row.order_number && <p className="text-[10px] font-mono text-slate-400">{row.order_number}</p>}
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono font-semibold text-slate-800">{row.coupon_code || "—"}</span>
                    {row.discount_type && (
                      <p className="text-[10px] text-slate-400 mt-0.5">{discountLabel(row)}</p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${
                      row.upgrade_type === "ongoing_upgrade"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700"
                    }`}>
                      {upgradeTypeLabel(row.upgrade_type)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600">
                    {row.base_amount > 0 ? `${row.currency} ${row.base_amount.toFixed(2)}` : <span className="text-slate-300">—</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {row.discount_amount > 0
                      ? <span className="text-red-600 font-medium">-{row.currency} {row.discount_amount.toFixed(2)}</span>
                      : <span className="text-slate-300">—</span>}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-slate-900">
                    {row.currency} {row.final_amount.toFixed(2)}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${
                      row.status === "paid" ? "bg-emerald-100 text-emerald-700"
                      : row.status === "pending_payment" ? "bg-amber-100 text-amber-700"
                      : "bg-slate-100 text-slate-500"
                    }`}>{row.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-slate-50 border-t border-slate-200">
              <tr>
                <td colSpan={4} className="px-4 py-2 text-xs font-medium text-slate-500 text-right">Totals</td>
                <td className="px-4 py-2 text-right text-xs font-semibold text-slate-700">
                  {rows[0]?.currency} {rows.reduce((s, r) => s + r.base_amount, 0).toFixed(2)}
                </td>
                <td className="px-4 py-2 text-right text-xs font-semibold text-red-600">
                  -{rows[0]?.currency} {rows.reduce((s, r) => s + r.discount_amount, 0).toFixed(2)}
                </td>
                <td className="px-4 py-2 text-right text-xs font-semibold text-emerald-700">
                  {rows[0]?.currency} {rows.reduce((s, r) => s + r.final_amount, 0).toFixed(2)}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Main PlansTab ────────────────────────────────────────────────────────────
export function PlansTab() {
  return (
    <div data-testid="plans-tab">
      <Tabs defaultValue="plans">
        <TabsList className="mb-4">
          <TabsTrigger value="plans" data-testid="plans-section-plans">
            <LayoutList size={14} className="mr-1.5" />License Plans
          </TabsTrigger>
          <TabsTrigger value="rates" data-testid="plans-section-rates">
            <Zap size={14} className="mr-1.5" />One-Time Rates
          </TabsTrigger>
          <TabsTrigger value="coupons" data-testid="plans-section-coupons">
            <Gift size={14} className="mr-1.5" />Coupons
          </TabsTrigger>
          <TabsTrigger value="usage" data-testid="plans-section-usage">
            <BarChart2 size={14} className="mr-1.5" />Coupon Usage
          </TabsTrigger>
        </TabsList>
        <TabsContent value="plans"><PlansSection /></TabsContent>
        <TabsContent value="rates"><OneTimeRatesSection /></TabsContent>
        <TabsContent value="coupons"><CouponsSection /></TabsContent>
        <TabsContent value="usage"><CouponUsageSection /></TabsContent>
      </Tabs>
    </div>
  );
}
