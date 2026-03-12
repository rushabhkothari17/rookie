import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { AdminPageHeader } from "./shared/AdminPageHeader";

import { Plus, Pencil, Trash2, GripVertical, ChevronDown, ChevronUp, X } from "lucide-react";

const FILTER_TYPES = [
  { value: "category", label: "Category", description: "Filter by product category (uses existing categories)" },
  { value: "tag", label: "Tag", description: "Filter by product tags — set tags on products in the catalog editor" },
  { value: "price_range", label: "Price Range", description: "Filter by price brackets" },
  { value: "checkout_type", label: "Checkout Type", description: "Internal checkout, Enquiry Only, or External Link" },
  { value: "billing_type", label: "Billing Type", description: "One-off or Subscription payment" },
  { value: "plan_name", label: "Plan Name", description: "Filter by subscription plan name" },
  { value: "intake_field", label: "Intake Field", description: "Filter by a specific intake question field and option value" },
];

type FilterOption = { label: string; value: string };
type StoreFilter = {
  id: string;
  name: string;
  filter_type: string;
  options: FilterOption[];
  is_active: boolean;
  sort_order: number;
  show_count: boolean;
};

function FilterFormModal({
  filter,
  existingFilters,
  onClose,
  onSaved,
}: {
  filter: StoreFilter | null;
  existingFilters: StoreFilter[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!filter;
  const [name, setName] = useState(filter?.name || "");
  const [type, setType] = useState(filter?.filter_type || "category");
  const [options, setOptions] = useState<FilterOption[]>(filter?.options || []);
  const [showCount, setShowCount] = useState(filter?.show_count ?? true);
  const [isActive, setIsActive] = useState(filter?.is_active ?? true);
  const [newOptLabel, setNewOptLabel] = useState("");
  const [newOptValue, setNewOptValue] = useState("");
  const [saving, setSaving] = useState(false);

  // Issue 2: Category count check
  const [categoryCount, setCategoryCount] = useState<number | null>(null);
  const [checkingCategories, setCheckingCategories] = useState(false);

  // Issue 1: Plans for plan_name filter type
  const [plans, setPlans] = useState<{ id: string; name: string }[]>([]);

  useEffect(() => {
    if (type === "category") {
      setCheckingCategories(true);
      api.get("/admin/categories")
        .then(r => {
          const cats = r.data.categories || [];
          setCategoryCount(cats.filter((c: any) => c.is_active !== false).length);
        })
        .catch(() => setCategoryCount(0))
        .finally(() => setCheckingCategories(false));
    } else {
      setCategoryCount(null);
    }
  }, [type]);

  useEffect(() => {
    if (type === "plan_name") {
      api.get("/partner/plans/public")
        .then(r => setPlans(r.data.plans || []))
        .catch(() => setPlans([]));
    }
  }, [type]);

  const addOption = () => {
    if (!newOptLabel.trim()) return;
    const value = newOptValue.trim() || newOptLabel.toLowerCase().replace(/\s+/g, "-");
    setOptions(prev => [...prev, { label: newOptLabel.trim(), value }]);
    setNewOptLabel(""); setNewOptValue("");
  };

  const removeOption = (idx: number) => setOptions(prev => prev.filter((_, i) => i !== idx));

  const togglePlanOption = (plan: { id: string; name: string }) => {
    const existing = options.find(o => o.value === plan.id);
    if (existing) {
      setOptions(prev => prev.filter(o => o.value !== plan.id));
    } else {
      setOptions(prev => [...prev, { label: plan.name, value: plan.id }]);
    }
  };

  const handleSave = async () => {
    if (!name.trim()) { toast.error("Filter name is required"); return; }
    // Issue 3: Name length check
    if (name.trim().length > 100) { toast.error("Filter name must be 100 characters or less"); return; }
    if (!type) { toast.error("Filter type is required"); return; }

    // Issue 2: Block if category type but no categories
    if (type === "category" && categoryCount === 0) {
      toast.error("No product categories exist. Create categories before adding a Category filter.");
      return;
    }

    // Issue 4: Duplicate name check (client-side guard before server call)
    const nameConflict = existingFilters.find(
      f => f.name.toLowerCase() === name.trim().toLowerCase() && f.id !== filter?.id
    );
    if (nameConflict) {
      toast.error(`A filter named "${name.trim()}" already exists`);
      return;
    }

    // Issue 5: Flush pending option input before saving
    const finalOptions = [...options];
    if (newOptLabel.trim()) {
      const val = newOptValue.trim() || newOptLabel.toLowerCase().replace(/\s+/g, "-");
      finalOptions.push({ label: newOptLabel.trim(), value: val });
    }

    setSaving(true);
    try {
      const payload = { name: name.trim(), filter_type: type, options: finalOptions, is_active: isActive, show_count: showCount };
      if (isEdit) {
        await api.put(`/admin/store-filters/${filter.id}`, payload);
        toast.success("Filter updated");
      } else {
        await api.post("/admin/store-filters", { ...payload, sort_order: 0 });
        toast.success("Filter created");
      }
      onSaved();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  };

  const needsManualOptions = type === "tag" || type === "price_range" || type === "intake_field";
  const canSave = !(type === "category" && categoryCount === 0 && !checkingCategories);

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Edit Filter — ${filter?.name}` : "New Filter"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div className="space-y-2">
            <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em] block">Filter Name <span className="text-red-400">*</span></label>
            <Input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Service Type, Price Range"
              maxLength={100}
              data-testid="filter-name-input"
            />
            {name.length > 80 && (
              <p className="text-xs text-amber-500 text-right">{name.length}/100 characters</p>
            )}
          </div>
          <div className="space-y-2">
            <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em] block">Filter Type <span className="text-red-400">*</span></label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger data-testid="filter-type-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {FILTER_TYPES.map(ft => (
                  <SelectItem key={ft.value} value={ft.value}>
                    <div>
                      <div className="font-medium text-sm">{ft.label}</div>
                      <div className="text-xs text-slate-400">{ft.description}</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {type === "category" && (
            <div className={`rounded-lg p-3 text-xs space-y-1 ${categoryCount === 0 && !checkingCategories ? "bg-red-50 text-red-700 border border-red-200" : "bg-blue-50 text-blue-700"}`}>
              {checkingCategories ? (
                <p>Checking categories…</p>
              ) : categoryCount === 0 ? (
                <>
                  <p className="font-semibold">No product categories found.</p>
                  <p>You need at least one product category before creating a Category filter. Go to <strong>Products → Categories</strong> to add one.</p>
                </>
              ) : (
                <p>Uses your existing product categories automatically. No options needed. ({categoryCount} categories found)</p>
              )}
            </div>
          )}

          {type === "checkout_type" && (
            <div className="bg-blue-50 rounded-lg p-3 text-xs text-blue-700 space-y-1">
              <p className="font-semibold">Auto-generates 3 options — no manual entry needed:</p>
              <ul className="list-disc list-inside text-blue-600 space-y-0.5">
                <li><strong>Internal Checkout</strong> — products with direct purchase</li>
                <li><strong>Enquiry Only</strong> — products requiring a sales enquiry</li>
                <li><strong>External Link</strong> — products that redirect to an external URL</li>
              </ul>
            </div>
          )}

          {type === "billing_type" && (
            <div className="bg-blue-50 rounded-lg p-3 text-xs text-blue-700 space-y-1">
              <p className="font-semibold">Auto-generates 2 options — no manual entry needed:</p>
              <ul className="list-disc list-inside text-blue-600 space-y-0.5">
                <li><strong>One-off</strong> — single payment products</li>
                <li><strong>Subscription</strong> — recurring payment products</li>
              </ul>
            </div>
          )}

          {type === "plan_name" && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-600">Select Plans to Include</label>
              {plans.length === 0 ? (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700">
                  <p className="font-semibold">No public plans found.</p>
                  <p>Create public plans first (Admin → Plans) or add options manually.</p>
                </div>
              ) : (
                <div className="space-y-1.5 max-h-40 overflow-y-auto border border-slate-200 rounded-lg p-3 bg-slate-50">
                  {plans.map(plan => {
                    const selected = options.some(o => o.value === plan.id);
                    return (
                      <label key={plan.id} className="flex items-center gap-2.5 cursor-pointer hover:bg-white rounded px-1 py-0.5 transition-colors">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => togglePlanOption(plan)}
                          className="rounded"
                          data-testid={`plan-option-${plan.id}`}
                        />
                        <span className="text-sm text-slate-700">{plan.name}</span>
                        {selected && <span className="text-[10px] text-emerald-600 ml-auto">Selected</span>}
                      </label>
                    );
                  })}
                </div>
              )}
              <p className="text-xs text-slate-400">{options.length} plan(s) selected as filter options.</p>
              {/* Also allow manual entry for plan names not in the dropdown */}
              <div className="flex gap-2">
                <Input value={newOptLabel} onChange={e => setNewOptLabel(e.target.value)} placeholder="Or type plan name" className="flex-1" onKeyDown={e => e.key === "Enter" && addOption()} />
                <Button size="sm" variant="outline" onClick={addOption} type="button"><Plus className="h-3.5 w-3.5" /></Button>
              </div>
            </div>
          )}

          {type === "tag" && (
            <div className="bg-amber-50 rounded-lg p-3 text-xs text-amber-800 space-y-1">
              <p className="font-semibold">How to associate products with this filter:</p>
              <ol className="list-decimal list-inside space-y-1 text-amber-700">
                <li>Add option(s) below — e.g. Label: <strong>"Express"</strong>, Value: <strong>"express"</strong></li>
                <li>Open each product in the catalog editor → <strong>General</strong> tab → <strong>Filter Tags</strong></li>
                <li>Add the tag value (e.g. <code className="bg-amber-100 px-1 rounded">express</code>) to that product</li>
              </ol>
            </div>
          )}

          {type === "intake_field" && (
            <div className="bg-violet-50 rounded-lg p-3 text-xs text-violet-800 space-y-1">
              <p className="font-semibold">How Intake Field filtering works:</p>
              <ol className="list-decimal list-inside space-y-1 text-violet-700">
                <li>Find the intake field's <strong>name</strong> attribute in your product's intake schema (e.g. <code className="bg-violet-100 px-1 rounded">service_region</code>)</li>
                <li>Note the exact <strong>option value</strong> for each option you want to filter by (e.g. <code className="bg-violet-100 px-1 rounded">australia</code>)</li>
                <li>Add options below using <strong>Value</strong> format: <code className="bg-violet-100 px-1 rounded">fieldname:optionvalue</code></li>
              </ol>
              <p className="text-violet-600 mt-1">Example: Label = <em>"Australia"</em>, Value = <code className="bg-violet-100 px-1 rounded">service_region:australia</code></p>
            </div>
          )}

          {needsManualOptions && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-600">Options</label>
              <div className="space-y-1.5 max-h-36 overflow-y-auto">
                {options.map((opt, i) => (
                  <div key={i} className="flex items-center gap-2 bg-slate-50 rounded px-2.5 py-1.5">
                    <span className="text-sm flex-1">{opt.label}</span>
                    <span className="text-xs text-slate-400 font-mono">{opt.value}</span>
                    <button onClick={() => removeOption(i)} className="text-slate-400 hover:text-red-500">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <Input value={newOptLabel} onChange={e => setNewOptLabel(e.target.value)} placeholder="Label" className="flex-1" onKeyDown={e => e.key === "Enter" && addOption()} />
                <Input
                  value={newOptValue}
                  onChange={e => setNewOptValue(e.target.value)}
                  placeholder={type === "intake_field" ? "fieldname:optionvalue" : "value (optional)"}
                  className="w-36 font-mono text-xs"
                />
                <Button size="sm" variant="outline" onClick={addOption} type="button"><Plus className="h-3.5 w-3.5" /></Button>
              </div>
              <p className="text-xs text-slate-400">
                {type === "intake_field"
                  ? "Value must be fieldname:optionvalue (e.g. service_region:australia)"
                  : "Press Enter or + to add. Value auto-generated from label if empty."}
              </p>
            </div>
          )}

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
              <input type="checkbox" checked={showCount} onChange={e => setShowCount(e.target.checked)} className="rounded" />
              Show product count next to option
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
              <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)} className="rounded" />
              Active (visible to customers)
            </label>
          </div>
        </div>
        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving || !canSave} data-testid="save-filter-btn">
            {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Filter"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function FiltersTab() {
  const [filters, setFilters] = useState<StoreFilter[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editFilter, setEditFilter] = useState<StoreFilter | null>(null);
  const [deleteFilter, setDeleteFilter] = useState<StoreFilter | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/store-filters");
      setFilters(data.filters || []);
    } catch { toast.error("Failed to load filters"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async () => {
    if (!deleteFilter) return;
    try {
      await api.delete(`/admin/store-filters/${deleteFilter.id}`);
      toast.success("Filter deleted");
      setDeleteFilter(null);
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  const toggleActive = async (f: StoreFilter) => {
    try {
      await api.put(`/admin/store-filters/${f.id}`, { is_active: !f.is_active });
      load();
    } catch { toast.error("Update failed"); }
  };

  const moveFilter = async (idx: number, dir: -1 | 1) => {
    const newFilters = [...filters];
    const swapIdx = idx + dir;
    if (swapIdx < 0 || swapIdx >= newFilters.length) return;
    [newFilters[idx], newFilters[swapIdx]] = [newFilters[swapIdx], newFilters[idx]];
    const reorderPayload = newFilters.map((f, i) => ({ id: f.id, sort_order: i }));
    setFilters(newFilters);
    try { await api.patch("/admin/store-filters/reorder", reorderPayload); }
    catch { load(); }
  };

  const typeLabel = (t: string) => FILTER_TYPES.find(f => f.value === t)?.label || t;

  return (
    <div className="space-y-4" data-testid="filters-tab">
      <AdminPageHeader
        title="Customer Filters"
        subtitle="Configure the filters shown to customers in your storefront product listing."
        actions={
          <Button size="sm" onClick={() => setShowCreate(true)} data-testid="create-filter-btn">
            <Plus className="h-3.5 w-3.5 mr-1.5" /> New Filter
          </Button>
        }
      />

      {/* Filter list */}
      {loading ? (
        <div className="py-12 text-center text-slate-400">Loading…</div>
      ) : filters.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-slate-200 py-14 text-center bg-white">
          <p className="text-slate-500 font-medium">No filters configured yet</p>
          <p className="text-slate-400 text-sm mt-1">Create your first filter to let customers narrow down products.</p>
          <Button size="sm" className="mt-4" onClick={() => setShowCreate(true)}>Create Filter</Button>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
          {filters.map((f, idx) => (
            <div
              key={f.id}
              className={`px-4 py-3 flex items-center gap-3 border-b border-slate-100 last:border-0 transition-colors ${f.is_active ? "bg-white hover:bg-slate-50/50" : "bg-slate-50/60 opacity-60"}`}
              data-testid={`filter-row-${f.id}`}
            >
              <div className="flex flex-col gap-0.5">
                <button onClick={() => moveFilter(idx, -1)} disabled={idx === 0} className="text-slate-300 hover:text-slate-500 disabled:opacity-20 leading-none">
                  <ChevronUp className="h-3 w-3" />
                </button>
                <button onClick={() => moveFilter(idx, 1)} disabled={idx === filters.length - 1} className="text-slate-300 hover:text-slate-500 disabled:opacity-20 leading-none">
                  <ChevronDown className="h-3 w-3" />
                </button>
              </div>
              <GripVertical className="h-4 w-4 text-slate-300 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-slate-800">{f.name}</span>
                  <Badge className="text-[10px] bg-slate-100 text-slate-500">{typeLabel(f.filter_type)}</Badge>
                  {!f.is_active && <Badge className="text-[10px] bg-amber-50 text-amber-600">Hidden</Badge>}
                </div>
                {f.options.length > 0 && (
                  <div className="flex gap-1 mt-1 flex-wrap">
                    {f.options.slice(0, 5).map((opt, oi) => (
                      <span key={oi} className="text-[11px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full">{opt.label}</span>
                    ))}
                    {f.options.length > 5 && <span className="text-[11px] text-slate-400">+{f.options.length - 5} more</span>}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  role="switch" aria-checked={f.is_active}
                  onClick={() => toggleActive(f)}
                  data-testid={`toggle-filter-${f.id}`}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full border-2 border-transparent transition-colors ${f.is_active ? "bg-emerald-500" : "bg-slate-200"}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${f.is_active ? "translate-x-4" : "translate-x-0"}`} />
                </button>
                <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => setEditFilter(f)} data-testid={`edit-filter-${f.id}`}>
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-red-400 hover:text-red-600" onClick={() => setDeleteFilter(f)} data-testid={`delete-filter-${f.id}`}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-400">
        Filters appear in the customer-facing storefront. Use the arrows to reorder them. Toggle on/off to show or hide.
      </p>

      {/* Modals */}
      {showCreate && (
        <FilterFormModal
          filter={null}
          existingFilters={filters}
          onClose={() => setShowCreate(false)}
          onSaved={() => { setShowCreate(false); load(); }}
        />
      )}
      {editFilter && (
        <FilterFormModal
          filter={editFilter}
          existingFilters={filters}
          onClose={() => setEditFilter(null)}
          onSaved={() => { setEditFilter(null); load(); }}
        />
      )}

      {deleteFilter && (
        <AlertDialog open onOpenChange={() => setDeleteFilter(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete "{deleteFilter.name}"?</AlertDialogTitle>
              <AlertDialogDescription>This filter will be removed from the storefront.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={handleDelete} data-testid="confirm-delete-filter">
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}
