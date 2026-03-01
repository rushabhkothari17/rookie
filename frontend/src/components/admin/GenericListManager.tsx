import { useState, useEffect } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, RefreshCw } from "lucide-react";
import { invalidatePlatformListCache } from "@/hooks/usePlatformList";

interface Props {
  /** Admin CRUD endpoint (without /api prefix), e.g. "admin/platform/partner-types" */
  adminSlug: string;
  /** Cache slug used in usePlatformList, e.g. "partner-types" */
  cacheSlug: string;
  label: string;
  description?: string;
  inputPlaceholder?: string;
  testId?: string;
}

export function GenericListManager({ adminSlug, cacheSlug, label, description, inputPlaceholder, testId }: Props) {
  const [items, setItems] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [newValue, setNewValue] = useState("");
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get(`/${adminSlug}`);
      setItems(r.data.values || []);
    } catch {
      toast.error(`Failed to load ${label}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line

  const handleAdd = async () => {
    const val = newValue.trim();
    if (!val) return;
    setAdding(true);
    try {
      const r = await api.post(`/${adminSlug}`, { value: val });
      setItems(r.data.values || []);
      setNewValue("");
      invalidatePlatformListCache(cacheSlug);
      toast.success(`"${val}" added`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || `Failed to add item`);
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (item: string) => {
    setRemoving(item);
    try {
      const encoded = encodeURIComponent(item);
      const r = await api.delete(`/${adminSlug}/${encoded}`);
      setItems(r.data.values || []);
      invalidatePlatformListCache(cacheSlug);
      toast.success(`"${item}" removed`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || `Failed to remove item`);
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className="space-y-6" data-testid={testId || `list-manager-${cacheSlug}`}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{label}</h2>
          {description && <p className="text-sm text-slate-500 mt-0.5">{description}</p>}
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid={`refresh-${cacheSlug}-btn`}>
          <RefreshCw size={14} className={loading ? "animate-spin mr-1.5" : "mr-1.5"} /> Refresh
        </Button>
      </div>

      {/* Add item */}
      <div className="flex gap-2 max-w-sm">
        <Input
          placeholder={inputPlaceholder || `Add new ${label.toLowerCase()} value`}
          value={newValue}
          onChange={e => setNewValue(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleAdd()}
          data-testid={`new-${cacheSlug}-input`}
        />
        <Button onClick={handleAdd} disabled={adding || !newValue.trim()} data-testid={`add-${cacheSlug}-btn`}>
          <Plus size={14} className="mr-1.5" />Add
        </Button>
      </div>

      {/* List */}
      {loading ? (
        <div className="text-sm text-slate-400">Loading…</div>
      ) : items.length === 0 ? (
        <div className="text-sm text-slate-400">No items yet. Add one above.</div>
      ) : (
        <div className="flex flex-wrap gap-2" data-testid={`${cacheSlug}-list`}>
          {items.map(item => (
            <div
              key={item}
              className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 group"
              data-testid={`${cacheSlug}-item-${item}`}
            >
              <span className="text-sm text-slate-800">{item}</span>
              <button
                onClick={() => handleRemove(item)}
                disabled={removing === item}
                className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-500 transition-opacity"
                data-testid={`remove-${cacheSlug}-${item}`}
                title={`Remove ${item}`}
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-400">
        {items.length} {items.length === 1 ? "item" : "items"} configured. Changes take effect immediately across all partner org forms.
      </p>
    </div>
  );
}
