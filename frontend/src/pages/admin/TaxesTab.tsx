import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/sonner";
import { Trash2, Plus, ChevronDown, ChevronUp, Search, Edit2, Check, X } from "lucide-react";
import api from "@/lib/api";

const COUNTRIES = [
  { code: "CA", name: "Canada" },
  { code: "US", name: "United States" },
  { code: "GB", name: "United Kingdom" },
  { code: "AU", name: "Australia" },
  { code: "IN", name: "India" },
  { code: "AT", name: "Austria" },
  { code: "BE", name: "Belgium" },
  { code: "FR", name: "France" },
  { code: "DE", name: "Germany" },
  { code: "IE", name: "Ireland" },
  { code: "IT", name: "Italy" },
  { code: "NL", name: "Netherlands" },
  { code: "PL", name: "Poland" },
  { code: "PT", name: "Portugal" },
  { code: "ES", name: "Spain" },
  { code: "SE", name: "Sweden" },
];

const CONDITION_FIELDS = [
  { value: "country", label: "Customer Country" },
  { value: "state", label: "Customer State/Province" },
  { value: "email", label: "Customer Email" },
  { value: "company_name", label: "Company Name" },
];

const OPERATORS = [
  { value: "equals", label: "equals" },
  { value: "not_equals", label: "does not equal" },
  { value: "contains", label: "contains" },
  { value: "not_contains", label: "does not contain" },
  { value: "empty", label: "is empty" },
  { value: "not_empty", label: "is not empty" },
];

// ── Tax Settings Panel ─────────────────────────────────────────────────────────

function TaxSettingsPanel() {
  const [settings, setSettings] = useState<any>({ enabled: false, country: "", state: "" });
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/admin/taxes/settings").then((r) => {
      setSettings(r.data.tax_settings || {});
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/api/admin/taxes/settings", settings);
      toast.success("Tax settings saved");
    } catch {
      toast.error("Failed to save tax settings");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-sm text-slate-500 py-4">Loading...</div>;

  return (
    <div className="space-y-6 max-w-lg">
      <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-5">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Tax Collection</h3>
          <p className="text-xs text-slate-500 mt-1">
            Enable to automatically calculate and add tax at checkout based on your location and customer location.
          </p>
        </div>

        <div className="flex items-center justify-between">
          <Label className="text-sm">Enable Tax Collection</Label>
          <Switch
            data-testid="tax-enabled-toggle"
            checked={!!settings.enabled}
            onCheckedChange={(v) => setSettings({ ...settings, enabled: v })}
          />
        </div>

        {settings.enabled && (
          <>
            <div className="space-y-1.5">
              <Label className="text-sm">Your Business Country <span className="text-red-500">*</span></Label>
              <Select
                value={settings.country || ""}
                onValueChange={(v) => setSettings({ ...settings, country: v })}
              >
                <SelectTrigger data-testid="tax-country-select">
                  <SelectValue placeholder="Select country" />
                </SelectTrigger>
                <SelectContent>
                  {COUNTRIES.map((c) => (
                    <SelectItem key={c.code} value={c.code}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-slate-400">Used to determine which tax rules apply (destination-based).</p>
            </div>

            {(settings.country === "CA" || settings.country === "US") && (
              <div className="space-y-1.5">
                <Label className="text-sm">
                  Your {settings.country === "CA" ? "Province" : "State"} Code
                </Label>
                <Input
                  data-testid="tax-state-input"
                  placeholder={settings.country === "CA" ? "e.g. ON, BC, QC" : "e.g. CA, NY, TX"}
                  value={settings.state || ""}
                  onChange={(e) => setSettings({ ...settings, state: e.target.value.toUpperCase() })}
                  maxLength={3}
                  className="w-40"
                />
                <p className="text-xs text-slate-400">
                  {settings.country === "CA"
                    ? "Required for correct GST/HST/PST calculation."
                    : "Used for nexus determination."}
                </p>
              </div>
            )}
          </>
        )}

        <Button data-testid="tax-settings-save-btn" onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save Settings"}
        </Button>
      </div>

      {settings.enabled && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 space-y-1.5">
          <p className="font-semibold text-slate-700">How tax is calculated:</p>
          <ul className="list-disc pl-4 space-y-1">
            <li>Customers marked <strong>Tax Exempt</strong> are never charged tax.</li>
            <li>Partner override rules take highest priority.</li>
            <li>Otherwise, destination-based rules apply (CA, US, GB, AU, IN, EU).</li>
            <li>Tax is calculated on the subtotal after discounts, before the card processing fee.</li>
            <li>Cross-border transactions (outside your tax jurisdiction) are 0%.</li>
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Tax Table Browser ──────────────────────────────────────────────────────────

function TaxTablePanel() {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterCountry, setFilterCountry] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editRate, setEditRate] = useState("");
  const [editLabel, setEditLabel] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const params = filterCountry ? `?country_code=${filterCountry}` : "";
    const r = await api.get(`/api/admin/taxes/tables${params}`);
    setEntries(r.data.entries || []);
    setLoading(false);
  }, [filterCountry]);

  useEffect(() => { load(); }, [load]);

  const startEdit = (entry: any) => {
    setEditingKey(`${entry.country_code}-${entry.state_code}`);
    setEditRate(String(Math.round(entry.rate * 10000) / 100));
    setEditLabel(entry.label || "");
  };

  const saveEdit = async (entry: any) => {
    try {
      await api.put(
        `/api/admin/taxes/tables/${entry.country_code}/${entry.state_code || "_"}`,
        { rate: parseFloat(editRate) / 100, label: editLabel }
      );
      toast.success("Rate updated");
      setEditingKey(null);
      load();
    } catch {
      toast.error("Failed to update rate");
    }
  };

  const filtered = entries.filter((e) => {
    if (!searchTerm) return true;
    const s = searchTerm.toLowerCase();
    return e.state_name?.toLowerCase().includes(s) || e.state_code?.toLowerCase().includes(s);
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center">
        <Select value={filterCountry} onValueChange={setFilterCountry}>
          <SelectTrigger className="w-44" data-testid="tax-table-country-filter">
            <SelectValue placeholder="All Countries" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All Countries</SelectItem>
            {COUNTRIES.map((c) => <SelectItem key={c.code} value={c.code}>{c.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search by state/province..."
            className="pl-9"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <span className="text-xs text-slate-400">{filtered.length} entries</span>
      </div>

      {loading ? (
        <div className="text-sm text-slate-500 py-8 text-center">Loading tax table...</div>
      ) : (
        <div className="rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase">Country</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase">State/Region</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase">Tax Type</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase">Rate</th>
                <th className="px-4 py-2.5 w-20"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((entry) => {
                const key = `${entry.country_code}-${entry.state_code}`;
                const isEditing = editingKey === key;
                return (
                  <tr key={key} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-2.5 font-mono text-xs font-semibold text-slate-700">{entry.country_code}</td>
                    <td className="px-4 py-2.5 text-slate-700">{entry.state_name || "—"} {entry.state_code && <span className="text-xs text-slate-400 font-mono ml-1">({entry.state_code})</span>}</td>
                    <td className="px-4 py-2.5">
                      {isEditing ? (
                        <Input value={editLabel} onChange={(e) => setEditLabel(e.target.value)} className="h-7 w-28 text-xs" />
                      ) : (
                        <Badge variant="outline" className="text-xs">{entry.label}</Badge>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {isEditing ? (
                        <div className="flex items-center justify-end gap-1">
                          <Input value={editRate} onChange={(e) => setEditRate(e.target.value)} className="h-7 w-16 text-xs text-right" />
                          <span className="text-xs text-slate-400">%</span>
                        </div>
                      ) : (
                        <span className="font-semibold text-slate-900">{(entry.rate * 100).toFixed(2)}%</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      {isEditing ? (
                        <div className="flex gap-1 justify-end">
                          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => saveEdit(entry)}>
                            <Check className="h-3.5 w-3.5 text-green-600" />
                          </Button>
                          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEditingKey(null)}>
                            <X className="h-3.5 w-3.5 text-slate-400" />
                          </Button>
                        </div>
                      ) : (
                        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => startEdit(entry)}>
                          <Edit2 className="h-3.5 w-3.5 text-slate-400" />
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-slate-400">No entries found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Override Rules ─────────────────────────────────────────────────────────────

const emptyRule = { name: "", tax_rate: 0, tax_name: "", priority: 0, conditions: [] };
const emptyCondition = { field: "country", operator: "equals", value: "" };

function OverrideRulesPanel() {
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<any>({ ...emptyRule, conditions: [] });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const r = await api.get("/api/admin/taxes/overrides");
    setRules(r.data.rules || []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const startCreate = () => {
    setEditingId(null);
    setForm({ ...emptyRule, conditions: [] });
    setShowForm(true);
  };

  const startEdit = (rule: any) => {
    setEditingId(rule.id);
    setForm({ ...rule });
    setShowForm(true);
  };

  const addCondition = () => setForm((f: any) => ({ ...f, conditions: [...f.conditions, { ...emptyCondition }] }));
  const removeCondition = (i: number) => setForm((f: any) => ({ ...f, conditions: f.conditions.filter((_: any, idx: number) => idx !== i) }));
  const updateCondition = (i: number, key: string, val: string) =>
    setForm((f: any) => ({
      ...f,
      conditions: f.conditions.map((c: any, idx: number) => idx === i ? { ...c, [key]: val } : c),
    }));

  const save = async () => {
    if (!form.name.trim()) return toast.error("Rule name is required");
    if (!form.tax_name.trim()) return toast.error("Tax name is required");
    setSaving(true);
    try {
      const payload = {
        ...form,
        tax_rate: parseFloat(form.tax_rate) / 100,
        priority: parseInt(form.priority) || 0,
      };
      if (editingId) {
        await api.put(`/api/admin/taxes/overrides/${editingId}`, payload);
        toast.success("Override rule updated");
      } else {
        await api.post("/api/admin/taxes/overrides", payload);
        toast.success("Override rule created");
      }
      setShowForm(false);
      load();
    } catch {
      toast.error("Failed to save override rule");
    } finally {
      setSaving(false);
    }
  };

  const deleteRule = async (id: string) => {
    if (!confirm("Delete this override rule?")) return;
    try {
      await api.delete(`/api/admin/taxes/overrides/${id}`);
      toast.success("Override rule deleted");
      load();
    } catch {
      toast.error("Failed to delete rule");
    }
  };

  if (loading) return <div className="text-sm text-slate-500 py-4">Loading...</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-600">
            Override rules let you set custom tax rates for specific customers (e.g. zero-rate for a particular country, or a special rate for certain companies).
          </p>
          <p className="text-xs text-slate-400 mt-1">Rules are evaluated highest priority first. The first matching rule wins.</p>
        </div>
        <Button size="sm" onClick={startCreate} data-testid="add-override-rule-btn">
          <Plus className="h-4 w-4 mr-1.5" /> Add Rule
        </Button>
      </div>

      {showForm && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 space-y-4">
          <h4 className="text-sm font-semibold text-slate-900">
            {editingId ? "Edit Override Rule" : "New Override Rule"}
          </h4>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs">Rule Name <span className="text-red-500">*</span></Label>
              <Input
                data-testid="override-rule-name"
                placeholder="e.g. Zero-rate UK customers"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Priority</Label>
              <Input
                type="number"
                placeholder="0"
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value })}
                className="w-24"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs">Tax Name <span className="text-red-500">*</span></Label>
              <Input
                data-testid="override-rule-tax-name"
                placeholder="e.g. VAT, GST, Zero-rated"
                value={form.tax_name}
                onChange={(e) => setForm({ ...form, tax_name: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Tax Rate (%)</Label>
              <div className="flex items-center gap-1.5">
                <Input
                  data-testid="override-rule-rate"
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  placeholder="0"
                  value={form.tax_rate}
                  onChange={(e) => setForm({ ...form, tax_rate: e.target.value })}
                  className="w-24"
                />
                <span className="text-sm text-slate-500">%</span>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Conditions (all must match)</Label>
              <Button variant="ghost" size="sm" onClick={addCondition} className="h-7 text-xs">
                <Plus className="h-3.5 w-3.5 mr-1" /> Add Condition
              </Button>
            </div>
            {form.conditions.length === 0 && (
              <p className="text-xs text-slate-400 italic">No conditions — this rule will match all customers.</p>
            )}
            {form.conditions.map((cond: any, i: number) => (
              <div key={i} className="flex gap-2 items-center bg-white rounded-lg border border-slate-200 px-3 py-2">
                <Select value={cond.field} onValueChange={(v) => updateCondition(i, "field", v)}>
                  <SelectTrigger className="h-7 text-xs w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CONDITION_FIELDS.map((f) => <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Select value={cond.operator} onValueChange={(v) => updateCondition(i, "operator", v)}>
                  <SelectTrigger className="h-7 text-xs w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {OPERATORS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                  </SelectContent>
                </Select>
                {!["empty", "not_empty"].includes(cond.operator) && (
                  <Input
                    className="h-7 text-xs flex-1"
                    placeholder="Value"
                    value={cond.value}
                    onChange={(e) => updateCondition(i, "value", e.target.value)}
                  />
                )}
                <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0" onClick={() => removeCondition(i)}>
                  <X className="h-3.5 w-3.5 text-slate-400" />
                </Button>
              </div>
            ))}
          </div>

          <div className="flex gap-2 pt-2">
            <Button size="sm" onClick={save} disabled={saving} data-testid="override-rule-save-btn">
              {saving ? "Saving..." : editingId ? "Update Rule" : "Create Rule"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
          </div>
        </div>
      )}

      {rules.length === 0 && !showForm && (
        <div className="rounded-xl border border-dashed border-slate-300 py-10 text-center">
          <p className="text-sm text-slate-500">No override rules yet.</p>
          <p className="text-xs text-slate-400 mt-1">Add rules to customize tax rates for specific customers.</p>
        </div>
      )}

      {rules.length > 0 && (
        <div className="space-y-2">
          {rules.map((rule) => (
            <div key={rule.id} className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex-1 space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-900">{rule.name}</span>
                  <Badge variant="outline" className="text-xs">{rule.tax_name}</Badge>
                  <Badge className="text-xs bg-slate-100 text-slate-700">
                    {(rule.tax_rate * 100).toFixed(2)}%
                  </Badge>
                  {rule.priority > 0 && (
                    <Badge variant="secondary" className="text-xs">Priority {rule.priority}</Badge>
                  )}
                </div>
                {rule.conditions.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {rule.conditions.map((c: any, i: number) => (
                      <span key={i} className="text-xs bg-slate-100 text-slate-600 rounded px-2 py-0.5">
                        {c.field} {c.operator.replace("_", " ")} {c.value && `"${c.value}"`}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-xs text-slate-400 italic">Matches all customers</span>
                )}
              </div>
              <div className="flex gap-1 shrink-0">
                <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => startEdit(rule)}>
                  <Edit2 className="h-3.5 w-3.5 text-slate-400" />
                </Button>
                <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => deleteRule(rule.id)}>
                  <Trash2 className="h-3.5 w-3.5 text-red-400" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main TaxesTab Component ────────────────────────────────────────────────────

export function TaxesTab() {
  return (
    <div className="space-y-6" data-testid="taxes-tab">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Tax Management</h2>
        <p className="text-sm text-slate-500 mt-1">
          Configure tax collection, view global rates, and create custom override rules.
        </p>
      </div>

      <Tabs defaultValue="settings">
        <TabsList className="bg-slate-100">
          <TabsTrigger value="settings" data-testid="taxes-tab-settings">Tax Settings</TabsTrigger>
          <TabsTrigger value="table" data-testid="taxes-tab-table">Rate Table</TabsTrigger>
          <TabsTrigger value="overrides" data-testid="taxes-tab-overrides">Override Rules</TabsTrigger>
        </TabsList>

        <TabsContent value="settings" className="pt-5">
          <TaxSettingsPanel />
        </TabsContent>

        <TabsContent value="table" className="pt-5">
          <TaxTablePanel />
        </TabsContent>

        <TabsContent value="overrides" className="pt-5">
          <OverrideRulesPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
