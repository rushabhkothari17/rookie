import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/sonner";
import { Trash2, Plus, Search, Edit2, Check, X } from "lucide-react";
import api from "@/lib/api";

const COUNTRIES = [
  { code: "AL", name: "Albania" }, { code: "DZ", name: "Algeria" }, { code: "AR", name: "Argentina" },
  { code: "AM", name: "Armenia" }, { code: "AU", name: "Australia" }, { code: "AT", name: "Austria" },
  { code: "AZ", name: "Azerbaijan" }, { code: "BH", name: "Bahrain" }, { code: "BD", name: "Bangladesh" },
  { code: "BY", name: "Belarus" }, { code: "BE", name: "Belgium" }, { code: "BO", name: "Bolivia" },
  { code: "BA", name: "Bosnia & Herzegovina" }, { code: "BR", name: "Brazil" }, { code: "BG", name: "Bulgaria" },
  { code: "CA", name: "Canada" }, { code: "CL", name: "Chile" }, { code: "CN", name: "China" },
  { code: "CO", name: "Colombia" }, { code: "HR", name: "Croatia" }, { code: "CY", name: "Cyprus" },
  { code: "CZ", name: "Czech Republic" }, { code: "DK", name: "Denmark" }, { code: "EG", name: "Egypt" },
  { code: "EE", name: "Estonia" }, { code: "ET", name: "Ethiopia" }, { code: "FI", name: "Finland" },
  { code: "FR", name: "France" }, { code: "GE", name: "Georgia" }, { code: "DE", name: "Germany" },
  { code: "GH", name: "Ghana" }, { code: "GR", name: "Greece" }, { code: "GT", name: "Guatemala" },
  { code: "HN", name: "Honduras" }, { code: "HK", name: "Hong Kong" }, { code: "HU", name: "Hungary" },
  { code: "IS", name: "Iceland" }, { code: "IN", name: "India" }, { code: "ID", name: "Indonesia" },
  { code: "IE", name: "Ireland" }, { code: "IL", name: "Israel" }, { code: "IT", name: "Italy" },
  { code: "JM", name: "Jamaica" }, { code: "JP", name: "Japan" }, { code: "JO", name: "Jordan" },
  { code: "KZ", name: "Kazakhstan" }, { code: "KE", name: "Kenya" }, { code: "KW", name: "Kuwait" },
  { code: "LV", name: "Latvia" }, { code: "LB", name: "Lebanon" }, { code: "LT", name: "Lithuania" },
  { code: "LU", name: "Luxembourg" }, { code: "MK", name: "North Macedonia" }, { code: "MY", name: "Malaysia" },
  { code: "MT", name: "Malta" }, { code: "MX", name: "Mexico" }, { code: "MD", name: "Moldova" },
  { code: "MA", name: "Morocco" }, { code: "MZ", name: "Mozambique" }, { code: "NL", name: "Netherlands" },
  { code: "NZ", name: "New Zealand" }, { code: "NG", name: "Nigeria" }, { code: "NO", name: "Norway" },
  { code: "PK", name: "Pakistan" }, { code: "PA", name: "Panama" }, { code: "PY", name: "Paraguay" },
  { code: "PE", name: "Peru" }, { code: "PH", name: "Philippines" }, { code: "PL", name: "Poland" },
  { code: "PT", name: "Portugal" }, { code: "QA", name: "Qatar" }, { code: "RO", name: "Romania" },
  { code: "RU", name: "Russia" }, { code: "SA", name: "Saudi Arabia" }, { code: "RS", name: "Serbia" },
  { code: "SG", name: "Singapore" }, { code: "SK", name: "Slovakia" }, { code: "SI", name: "Slovenia" },
  { code: "ZA", name: "South Africa" }, { code: "KR", name: "South Korea" }, { code: "ES", name: "Spain" },
  { code: "LK", name: "Sri Lanka" }, { code: "SE", name: "Sweden" }, { code: "CH", name: "Switzerland" },
  { code: "TW", name: "Taiwan" }, { code: "TZ", name: "Tanzania" }, { code: "TH", name: "Thailand" },
  { code: "TN", name: "Tunisia" }, { code: "TR", name: "Turkey" }, { code: "UG", name: "Uganda" },
  { code: "UA", name: "Ukraine" }, { code: "AE", name: "United Arab Emirates" }, { code: "GB", name: "United Kingdom" },
  { code: "US", name: "United States" }, { code: "UY", name: "Uruguay" }, { code: "UZ", name: "Uzbekistan" },
  { code: "VN", name: "Vietnam" }, { code: "ZW", name: "Zimbabwe" },
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
    api.get("/admin/taxes/settings").then((r) => {
      setSettings(r.data.tax_settings || {});
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/admin/taxes/settings", settings);
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
          <input
            type="checkbox"
            data-testid="tax-enabled-toggle"
            checked={!!settings.enabled}
            onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })}
            className="h-4 w-4 rounded border-slate-300 accent-slate-900"
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
  const [filterCountry, setFilterCountry] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editRate, setEditRate] = useState("");
  const [editLabel, setEditLabel] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const params = filterCountry && filterCountry !== "all" ? `?country_code=${filterCountry}` : "";
    const r = await api.get(`/admin/taxes/tables${params}`);
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
        `/admin/taxes/tables/${entry.country_code}/${entry.state_code || "_"}`,
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
            <SelectItem value="all">All Countries</SelectItem>
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
    const r = await api.get("/admin/taxes/overrides");
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
        await api.put(`/admin/taxes/overrides/${editingId}`, payload);
        toast.success("Override rule updated");
      } else {
        await api.post("/admin/taxes/overrides", payload);
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
      await api.delete(`/admin/taxes/overrides/${id}`);
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

// ── Invoice Settings Panel ────────────────────────────────────────────────────

const PAYMENT_TERMS = ["Due on receipt", "Net 7", "Net 14", "Net 30", "Net 60"];
const TEMPLATE_OPTIONS = [
  { value: "classic",      label: "Classic — serif, clean monochrome" },
  { value: "modern",       label: "Modern — dark header, colored accents" },
  { value: "minimal",      label: "Minimal — whitespace, essentials only" },
  { value: "professional", label: "Professional — grid lines, dark header" },
  { value: "branded",      label: "Branded — logo area, gradient accent" },
];

function InvoiceSettingsPanel() {
  const [settings, setSettings] = useState<any>({ prefix: "INV", payment_terms: "Due on receipt", footer_notes: "", show_terms: true, template: "classic" });
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [customTemplates, setCustomTemplates] = useState<any[]>([]);
  const [showNewTemplate, setShowNewTemplate] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<any>(null);
  const [tmplForm, setTmplForm] = useState({ name: "", html_body: "" });

  useEffect(() => {
    api.get("/admin/taxes/invoice-settings").then(r => {
      setSettings(r.data.invoice_settings || {});
      setLoading(false);
    }).catch(() => setLoading(false));
    loadCustomTemplates();
  }, []);

  const loadCustomTemplates = () => {
    api.get("/admin/taxes/invoice-templates").then(r => setCustomTemplates(r.data.templates || [])).catch(() => {});
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/admin/taxes/invoice-settings", settings);
      toast.success("Invoice settings saved");
    } catch { toast.error("Failed to save invoice settings"); }
    finally { setSaving(false); }
  };

  const saveTemplate = async () => {
    if (!tmplForm.name.trim()) return toast.error("Template name is required");
    try {
      if (editingTemplate) {
        await api.put(`/admin/taxes/invoice-templates/${editingTemplate.id}`, tmplForm);
        toast.success("Template updated");
      } else {
        await api.post("/admin/taxes/invoice-templates", tmplForm);
        toast.success("Template created");
      }
      setShowNewTemplate(false);
      setEditingTemplate(null);
      setTmplForm({ name: "", html_body: "" });
      loadCustomTemplates();
    } catch { toast.error("Failed to save template"); }
  };

  const deleteTemplate = async (id: string) => {
    if (!confirm("Delete this custom template?")) return;
    try {
      await api.delete(`/admin/taxes/invoice-templates/${id}`);
      toast.success("Template deleted");
      loadCustomTemplates();
    } catch { toast.error("Failed to delete template"); }
  };

  const startEditTemplate = (t: any) => {
    setEditingTemplate(t);
    setTmplForm({ name: t.name, html_body: t.html_body });
    setShowNewTemplate(true);
  };

  const STARTER_HTML = `<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;padding:40px;color:#1e293b">
  <h1>Invoice {{invoice_number}}</h1>
  <p>Date: {{order_date}} &bull; From: {{partner_name}}</p>
  <p>Bill To: {{customer_name}} ({{customer_email}})</p>
  <hr/>
  <p style="font-size:18px;font-weight:bold">Total: {{order_total}}</p>
  <p style="color:#64748b;font-size:12px">{{footer_notes}}</p>
</body></html>`;

  if (loading) return <div className="text-sm text-slate-500 py-4">Loading...</div>;

  return (
    <div className="space-y-6 max-w-lg">
      <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-5">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Invoice Configuration</h3>
          <p className="text-xs text-slate-500 mt-1">These settings apply to all invoices generated for your customers.</p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label className="text-xs">Invoice Prefix</Label>
            <Input data-testid="invoice-prefix-input" placeholder="INV" value={settings.prefix || ""} onChange={e => setSettings({ ...settings, prefix: e.target.value })} className="w-28" maxLength={10} />
            <p className="text-xs text-slate-400">e.g. INV → INV-AA-0001234</p>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Default Payment Terms</Label>
            <Select value={settings.payment_terms || "Due on receipt"} onValueChange={v => setSettings({ ...settings, payment_terms: v })}>
              <SelectTrigger data-testid="invoice-terms-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAYMENT_TERMS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Default Template</Label>
          <Select value={settings.template || "classic"} onValueChange={v => setSettings({ ...settings, template: v })}>
            <SelectTrigger data-testid="invoice-template-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TEMPLATE_OPTIONS.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Footer Notes</Label>
          <textarea
            data-testid="invoice-footer-input"
            className="w-full rounded-lg border border-slate-200 text-sm p-3 min-h-[80px] resize-none focus:outline-none focus:ring-1 focus:ring-slate-400"
            placeholder="e.g. Thank you for your business. Please contact us at billing@example.com for queries."
            value={settings.footer_notes || ""}
            onChange={e => setSettings({ ...settings, footer_notes: e.target.value })}
          />
        </div>
        <div className="flex items-center gap-3">
          <input type="checkbox" id="show-terms" checked={!!settings.show_terms} onChange={e => setSettings({ ...settings, show_terms: e.target.checked })} className="h-4 w-4 accent-slate-900" />
          <Label htmlFor="show-terms" className="text-sm cursor-pointer">Include Terms & Conditions on invoice</Label>
        </div>
        <Button data-testid="invoice-settings-save-btn" onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save Invoice Settings"}
        </Button>
      </div>

      {/* Custom Invoice Templates */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Custom Invoice Templates</h3>
            <p className="text-xs text-slate-500 mt-0.5">Create your own HTML templates visible only to your organisation.</p>
          </div>
          <Button size="sm" variant="outline" onClick={() => { setEditingTemplate(null); setTmplForm({ name: "", html_body: "" }); setShowNewTemplate(true); }} data-testid="new-custom-template-btn">
            <Plus className="h-3.5 w-3.5 mr-1.5" />New Template
          </Button>
        </div>

        {showNewTemplate && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Template Name <span className="text-red-500">*</span></Label>
              <Input value={tmplForm.name} onChange={e => setTmplForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Company Branded Template" data-testid="custom-template-name" />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs">HTML Body</Label>
                {!tmplForm.html_body && (
                  <button onClick={() => setTmplForm(f => ({ ...f, html_body: STARTER_HTML }))} className="text-xs text-blue-600 hover:underline">
                    Use starter template
                  </button>
                )}
              </div>
              <p className="text-xs text-slate-400">Variables: <code className="bg-slate-200 px-1 rounded">{"{{invoice_number}}"}</code> <code className="bg-slate-200 px-1 rounded">{"{{partner_name}}"}</code> <code className="bg-slate-200 px-1 rounded">{"{{customer_name}}"}</code> <code className="bg-slate-200 px-1 rounded">{"{{order_total}}"}</code> <code className="bg-slate-200 px-1 rounded">{"{{footer_notes}}"}</code></p>
              <textarea
                data-testid="custom-template-html"
                className="w-full rounded-lg border border-slate-200 text-xs font-mono p-3 min-h-[200px] resize-y focus:outline-none focus:ring-1 focus:ring-slate-400"
                value={tmplForm.html_body}
                onChange={e => setTmplForm(f => ({ ...f, html_body: e.target.value }))}
                placeholder="<!DOCTYPE html><html>...</html>"
              />
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={saveTemplate} data-testid="custom-template-save-btn">
                {editingTemplate ? "Update Template" : "Create Template"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { setShowNewTemplate(false); setEditingTemplate(null); }}>Cancel</Button>
            </div>
          </div>
        )}

        {customTemplates.length === 0 && !showNewTemplate ? (
          <div className="rounded-lg border border-dashed border-slate-300 py-6 text-center text-sm text-slate-400">
            No custom templates yet. They will appear in the invoice viewer alongside the 5 defaults.
          </div>
        ) : (
          <div className="space-y-2">
            {customTemplates.map(t => (
              <div key={t.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">{t.name}</p>
                  <p className="text-xs text-slate-400 mt-0.5">Created {(t.created_at || "").slice(0, 10)}</p>
                </div>
                <div className="flex gap-1">
                  <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => startEditTemplate(t)}>
                    <Edit2 className="h-3.5 w-3.5 text-slate-400" />
                  </Button>
                  <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => deleteTemplate(t.id)}>
                    <Trash2 className="h-3.5 w-3.5 text-red-400" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tax Summary Panel ─────────────────────────────────────────────────────────

function TaxSummaryPanel() {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [months, setMonths] = useState("12");

  useEffect(() => {
    api.get(`/admin/taxes/summary?months=${months}`).then(r => {
      setRows(r.data.summary || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [months]);

  // Group by month for display
  const byMonth: Record<string, any[]> = {};
  rows.forEach(r => {
    if (!byMonth[r.month]) byMonth[r.month] = [];
    byMonth[r.month].push(r);
  });

  const months_list = Object.keys(byMonth).sort((a, b) => b.localeCompare(a));
  const grandTotal = rows.reduce((s, r) => s + r.total_tax, 0);
  const totalOrders = rows.reduce((s, r) => s + r.order_count, 0);

  return (
    <div className="space-y-5" data-testid="tax-summary-panel">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Tax Collected Summary</h3>
          <p className="text-xs text-slate-500 mt-0.5">Aggregated from all paid orders with tax.</p>
        </div>
        <Select value={months} onValueChange={v => { setMonths(v); setLoading(true); }}>
          <SelectTrigger className="w-36 h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="3">Last 3 months</SelectItem>
            <SelectItem value="6">Last 6 months</SelectItem>
            <SelectItem value="12">Last 12 months</SelectItem>
            <SelectItem value="24">Last 24 months</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide">Total Tax Collected</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{grandTotal.toFixed(2)}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide">Taxed Orders</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{totalOrders}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide">Tax Types</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{new Set(rows.map(r => r.tax_name)).size}</p>
        </div>
      </div>

      {loading ? (
        <div className="text-sm text-slate-500 py-8 text-center">Loading summary...</div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 py-12 text-center">
          <p className="text-sm text-slate-500">No taxed orders found in this period.</p>
          <p className="text-xs text-slate-400 mt-1">Tax will appear here once orders with tax are placed.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {months_list.map(month => (
            <div key={month} className="rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2.5 flex items-center justify-between border-b border-slate-200">
                <span className="text-sm font-semibold text-slate-700">{month}</span>
                <span className="text-xs text-slate-400">
                  {byMonth[month].reduce((s, r) => s + r.order_count, 0)} orders ·{" "}
                  {byMonth[month][0]?.currency} {byMonth[month].reduce((s, r) => s + r.total_tax, 0).toFixed(2)} tax
                </span>
              </div>
              <table className="w-full text-sm">
                <tbody className="divide-y divide-slate-100">
                  {byMonth[month].map((row, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="px-4 py-2.5">
                        <span className="font-medium text-slate-800">{row.tax_name}</span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-500">{row.order_count} order{row.order_count !== 1 ? "s" : ""}</td>
                      <td className="px-4 py-2.5 text-right">
                        <span className="text-xs text-slate-400 mr-2">Revenue: {row.currency} {row.total_revenue.toFixed(2)}</span>
                        <span className="font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded text-xs">
                          Tax: {row.currency} {row.total_tax.toFixed(2)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
          <TabsTrigger value="invoices" data-testid="taxes-tab-invoices">Invoice Settings</TabsTrigger>
          <TabsTrigger value="summary" data-testid="taxes-tab-summary">Tax Summary</TabsTrigger>
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

        <TabsContent value="invoices" className="pt-5">
          <InvoiceSettingsPanel />
        </TabsContent>

        <TabsContent value="summary" className="pt-5">
          <TaxSummaryPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
