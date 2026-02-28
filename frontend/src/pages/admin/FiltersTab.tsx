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
import { Plus, Pencil, Trash2, GripVertical, ChevronDown, ChevronUp, X } from "lucide-react";

const FILTER_TYPES = [
  { value: "category", label: "Category", description: "Filter by product category (uses existing categories)" },
  { value: "tag", label: "Tag", description: "Filter by custom product tags" },
  { value: "price_range", label: "Price Range", description: "Filter by price brackets" },
  { value: "custom", label: "Custom", description: "Define your own filter name and options" },
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
  onClose,
  onSaved,
}: {
  filter: StoreFilter | null;
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

  const addOption = () => {
    if (!newOptLabel.trim()) return;
    const value = newOptValue.trim() || newOptLabel.toLowerCase().replace(/\s+/g, "-");
    setOptions(prev => [...prev, { label: newOptLabel.trim(), value }]);
    setNewOptLabel(""); setNewOptValue("");
  };

  const removeOption = (idx: number) => setOptions(prev => prev.filter((_, i) => i !== idx));

  const handleSave = async () => {
    if (!name.trim()) { toast.error("Filter name is required"); return; }
    setSaving(true);
    try {
      const payload = { name, filter_type: type, options, is_active: isActive, show_count: showCount };
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

  const needsOptions = type === "tag" || type === "price_range" || type === "custom";

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Edit Filter — ${filter?.name}` : "New Filter"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Filter Name *</label>
            <Input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Service Type, Price Range" data-testid="filter-name-input" />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Filter Type</label>
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
            <div className="bg-blue-50 rounded-lg p-3 text-xs text-blue-700">
              Uses your existing product categories automatically. No options needed.
            </div>
          )}

          {needsOptions && (
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
                <Input value={newOptValue} onChange={e => setNewOptValue(e.target.value)} placeholder="value (optional)" className="w-36 font-mono text-xs" />
                <Button size="sm" variant="outline" onClick={addOption} type="button"><Plus className="h-3.5 w-3.5" /></Button>
              </div>
              <p className="text-xs text-slate-400">Press Enter or + to add. Value auto-generated from label if empty.</p>
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
          <Button onClick={handleSave} disabled={saving} data-testid="save-filter-btn">
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
    <div className="space-y-5" data-testid="filters-tab">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Customer Filters</h2>
          <p className="text-sm text-slate-500">Configure the filters shown to customers in your storefront product listing.</p>
        </div>
        <Button onClick={() => setShowCreate(true)} data-testid="create-filter-btn">
          <Plus className="h-4 w-4 mr-1" /> New Filter
        </Button>
      </div>

      {/* Filter list */}
      {loading ? (
        <div className="py-12 text-center text-slate-400">Loading…</div>
      ) : filters.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-slate-200 py-14 text-center">
          <p className="text-slate-500 font-medium">No filters configured yet</p>
          <p className="text-slate-400 text-sm mt-1">Create your first filter to let customers narrow down products.</p>
          <Button className="mt-4" onClick={() => setShowCreate(true)}>Create Filter</Button>
        </div>
      ) : (
        <div className="space-y-2">
          {filters.map((f, idx) => (
            <div key={f.id} className={`rounded-xl border px-4 py-3 flex items-center gap-3 ${f.is_active ? "border-slate-200 bg-white" : "border-slate-100 bg-slate-50 opacity-60"}`} data-testid={`filter-row-${f.id}`}>
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
                      <span key={oi} className="text-[11px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">{opt.label}</span>
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
                <Button size="sm" variant="ghost" onClick={() => setEditFilter(f)} data-testid={`edit-filter-${f.id}`}>
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button size="sm" variant="ghost" className="text-red-400 hover:text-red-600" onClick={() => setDeleteFilter(f)} data-testid={`delete-filter-${f.id}`}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-400">
        Filters appear in the customer-facing storefront. Drag the arrows to reorder them. Toggle on/off to show or hide.
      </p>

      {/* Modals */}
      {showCreate && <FilterFormModal filter={null} onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />}
      {editFilter && <FilterFormModal filter={editFilter} onClose={() => setEditFilter(null)} onSaved={() => { setEditFilter(null); load(); }} />}

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
