import { useState, useEffect } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, RefreshCw, Coins } from "lucide-react";
import { invalidateCurrencyCache } from "@/hooks/useSupportedCurrencies";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export function CurrenciesTab() {
  const [currencies, setCurrencies] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [newCode, setNewCode] = useState("");
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/platform/currencies");
      setCurrencies(r.data.currencies || []);
    } catch {
      toast.error("Failed to load currencies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    const code = newCode.trim().toUpperCase();
    if (code.length !== 3) { toast.error("Currency code must be 3 letters"); return; }
    setAdding(true);
    try {
      const r = await api.post("/admin/platform/currencies", { code });
      setCurrencies(r.data.currencies);
      setNewCode("");
      invalidateCurrencyCache();
      toast.success(`${code} added`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to add currency");
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (code: string) => {
    setConfirmRemove(null);
    setRemoving(code);
    try {
      const r = await api.delete(`/admin/platform/currencies/${code}`);
      setCurrencies(r.data.currencies);
      invalidateCurrencyCache();
      toast.success(`${code} removed`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to remove currency");
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className="space-y-4" data-testid="currencies-tab">
      <AdminPageHeader
        title="Supported Currencies"
        subtitle={`${currencies.length} ${currencies.length === 1 ? "currency" : "currencies"} configured`}
        actions={
          <>
            <Input
              placeholder="e.g. CHF"
              value={newCode}
              onChange={e => setNewCode(e.target.value.toUpperCase())}
              maxLength={3}
              className="font-mono uppercase w-28 h-8 text-sm"
              onKeyDown={e => e.key === "Enter" && handleAdd()}
              data-testid="new-currency-input"
            />
            <Button size="sm" onClick={handleAdd} disabled={adding || newCode.trim().length !== 3} data-testid="add-currency-btn">
              <Plus size={14} className="mr-1" />Add Currency
            </Button>
            <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="refresh-currencies-btn">
              <RefreshCw size={14} className={loading ? "animate-spin mr-1" : "mr-1"} />Refresh
            </Button>
          </>
        }
      />

      <p className="text-sm text-slate-500 -mt-2">
        These currencies appear in all dropdowns across the platform — partner orgs, plans, subscriptions, orders and pricing.
      </p>

      {/* Currency list */}
      {loading ? (
        <div className="text-sm text-slate-400">Loading…</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2" data-testid="currencies-grid">
          {currencies.map(code => (
            <div
              key={code}
              className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 group"
              data-testid={`currency-item-${code}`}
            >
              <div className="flex items-center gap-2">
                <Coins size={13} className="text-slate-400 shrink-0" />
                <span className="font-mono font-semibold text-sm text-slate-800">{code}</span>
              </div>
              <button
                onClick={() => setConfirmRemove(code)}
                disabled={removing === code}
                className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-500 transition-opacity ml-2"
                data-testid={`remove-currency-${code}`}
                title={`Remove ${code}`}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-400">
        Removing a currency will not affect existing subscriptions or orders already using it.
      </p>

      {/* Confirmation dialog */}
      {confirmRemove && (
        <AlertDialog open onOpenChange={() => setConfirmRemove(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Remove {confirmRemove}?</AlertDialogTitle>
              <AlertDialogDescription>
                This will remove <strong>{confirmRemove}</strong> from the supported currencies list.
                Existing subscriptions and orders using this currency are not affected, but it will no longer appear in dropdowns.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                className="bg-red-600 hover:bg-red-700"
                onClick={() => handleRemove(confirmRemove)}
                data-testid="confirm-remove-currency-btn"
              >
                Remove
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}
