import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Lock, Trash2, ChevronUp, ChevronDown, Plus, Settings2, GripVertical, Eye, X, ChevronRight, Info } from "lucide-react";

// ── Visibility rule types ─────────────────────────────────────────────────────
export interface VisibilityConditionRow {
  depends_on: string;
  operator: "equals" | "not_equals" | "contains" | "not_contains" | "not_empty" | "empty";
  value: string;
}
export interface VisibilityGroup { logic: "AND" | "OR"; conditions: VisibilityConditionRow[]; }
export interface VisibilityRuleSet { top_logic: "AND" | "OR"; groups: VisibilityGroup[]; }

const VIS_OPERATORS = [
  { value: "equals",       label: "equals" },
  { value: "not_equals",   label: "does not equal" },
  { value: "contains",     label: "contains" },
  { value: "not_contains", label: "does not contain" },
  { value: "not_empty",    label: "is not empty" },
  { value: "empty",        label: "is empty" },
];
const NO_VAL_OPS = new Set(["not_empty", "empty"]);
const MAX_CONDS = 4; const MAX_GROUPS = 3;
const defCond = (): VisibilityConditionRow => ({ depends_on: "", operator: "equals", value: "" });
const defGroup = (): VisibilityGroup => ({ logic: "AND", conditions: [defCond()] });

function normRule(raw: any): VisibilityRuleSet {
  if (!raw) return { top_logic: "AND", groups: [defGroup()] };
  if (raw.groups && Array.isArray(raw.groups)) return raw as VisibilityRuleSet;
  if (raw.conditions && Array.isArray(raw.conditions))
    return { top_logic: "AND", groups: [{ logic: raw.logic || "AND", conditions: raw.conditions }] };
  return { top_logic: "AND", groups: [defGroup()] };
}

function visSummary(rule: any): string {
  try {
    const rs = normRule(rule);
    const total = rs.groups.reduce((s, g) => s + g.conditions.length, 0);
    if (!total) return "";
    const first = rs.groups[0]?.conditions[0];
    if (!first?.depends_on) return `${total} condition${total !== 1 ? "s" : ""}`;
    const opMap: Record<string, string> = { equals: "=", not_equals: "≠", contains: "has", not_contains: "!has", not_empty: "≠ empty", empty: "= empty" };
    const val = NO_VAL_OPS.has(first.operator) ? "" : ` "${first.value}"`;
    return `${first.depends_on} ${opMap[first.operator] ?? first.operator}${val}${total > 1 ? ` +${total - 1} more` : ""}`;
  } catch { return ""; }
}

function LogicPill({ value, onChange, small }: { value: "AND" | "OR"; onChange: (v: "AND" | "OR") => void; small?: boolean }) {
  const sz = small ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-0.5 text-[10px]";
  return (
    <div className="flex rounded overflow-hidden border border-blue-200">
      {(["AND", "OR"] as const).map(l => (
        <button key={l} type="button" onClick={() => onChange(l)}
          className={`${sz} font-bold transition-colors ${value === l ? "bg-blue-600 text-white" : "bg-white text-blue-500 hover:bg-blue-50"}`}>{l}</button>
      ))}
    </div>
  );
}

function VisibilityRuleEditor({ rule, onChange, otherFields }: {
  rule: VisibilityRuleSet | null | undefined;
  onChange: (r: VisibilityRuleSet | null) => void;
  otherFields: FormField[];
}) {
  const isOn = !!rule;
  const [expanded, setExpanded] = useState(false);
  const rs: VisibilityRuleSet = isOn ? normRule(rule) : { top_logic: "AND", groups: [defGroup()] };

  const toggle = (on: boolean) => { onChange(on ? rs : null); if (on) setExpanded(true); };
  const setTopLogic = (tl: "AND" | "OR") => onChange({ ...rs, top_logic: tl });
  const setGroupLogic = (gi: number, l: "AND" | "OR") =>
    onChange({ ...rs, groups: rs.groups.map((g, i) => i === gi ? { ...g, logic: l } : g) });
  const setCond = (gi: number, ci: number, p: Partial<VisibilityConditionRow>) =>
    onChange({ ...rs, groups: rs.groups.map((g, i) => i !== gi ? g : { ...g, conditions: g.conditions.map((c, j) => j !== ci ? c : { ...c, ...p }) }) });
  const addCond = (gi: number) => {
    if (rs.groups[gi].conditions.length >= MAX_CONDS) return;
    onChange({ ...rs, groups: rs.groups.map((g, i) => i !== gi ? g : { ...g, conditions: [...g.conditions, defCond()] }) });
  };
  const removeCond = (gi: number, ci: number) => {
    const ng = rs.groups.map((g, i) => i !== gi ? g : { ...g, conditions: g.conditions.filter((_, j) => j !== ci) }).filter(g => g.conditions.length > 0);
    onChange(ng.length ? { ...rs, groups: ng } : null);
  };
  const addGroup = () => { if (rs.groups.length >= MAX_GROUPS) return; onChange({ ...rs, groups: [...rs.groups, defGroup()] }); };
  const removeGroup = (gi: number) => { const ng = rs.groups.filter((_, i) => i !== gi); onChange(ng.length ? { ...rs, groups: ng } : null); };

  const eligible = otherFields.filter(f => f.key && f.type !== "signature" && f.type !== "terms_conditions");

  return (
    <div className="col-span-2 border-t border-slate-100 pt-2.5 mt-1 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Eye size={12} className="text-slate-400" />
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Visibility rule</span>
          {isOn && !expanded && (
            <span className="text-[10px] text-blue-500 italic">— {visSummary(rule)}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isOn && (
            <button type="button" onClick={() => setExpanded(v => !v)}
              className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-600">
              <ChevronRight size={11} className={`transition-transform ${expanded ? "rotate-90" : ""}`} />
              {expanded ? "Collapse" : "Edit"}
            </button>
          )}
          <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer select-none">
            <input type="checkbox" checked={isOn} onChange={e => toggle(e.target.checked)} className="w-3 h-3 rounded accent-slate-900" />
            {isOn ? "On" : "Off"}
          </label>
        </div>
      </div>

      {isOn && expanded && (
        <div className="space-y-3">
          <p className="text-[11px] text-blue-600 font-medium">Show this field only when:</p>
          {rs.groups.map((group, gi) => (
            <div key={gi}>
              {gi > 0 && (
                <div className="flex items-center gap-2 my-2">
                  <div className="flex-1 border-t border-dashed border-slate-300" />
                  <LogicPill value={rs.top_logic} onChange={setTopLogic} />
                  <div className="flex-1 border-t border-dashed border-slate-300" />
                </div>
              )}
              <div className="bg-blue-50/60 border border-blue-100 rounded-lg p-3 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-blue-500 uppercase tracking-wide">
                    {rs.groups.length > 1 ? `Group ${gi + 1}` : "Conditions"}
                  </span>
                  <div className="flex items-center gap-2">
                    {group.conditions.length > 1 && <LogicPill value={group.logic} onChange={l => setGroupLogic(gi, l)} small />}
                    {rs.groups.length > 1 && (
                      <button type="button" onClick={() => removeGroup(gi)} className="text-slate-300 hover:text-red-400"><X size={12} /></button>
                    )}
                  </div>
                </div>
                {group.conditions.map((cond, ci) => (
                  <div key={ci} className="space-y-2">
                    {ci > 0 && (
                      <div className="flex items-center gap-1.5 my-1">
                        <div className="flex-1 border-t border-blue-100" />
                        <span className="text-[9px] font-bold text-blue-400">{group.logic}</span>
                        <div className="flex-1 border-t border-blue-100" />
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[10px] text-slate-500 block mb-1">Field</label>
                        <Select value={cond.depends_on || ""} onValueChange={v => setCond(gi, ci, { depends_on: v })}>
                          <SelectTrigger className="h-7 text-xs"><SelectValue placeholder="Pick field…" /></SelectTrigger>
                          <SelectContent>
                            {eligible.map(f => <SelectItem key={f.id} value={f.key}>{f.label || f.key}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-500 block mb-1">Condition</label>
                        <div className="flex gap-1">
                          <Select value={cond.operator} onValueChange={v => setCond(gi, ci, { operator: v as any, value: NO_VAL_OPS.has(v) ? "" : cond.value })}>
                            <SelectTrigger className="h-7 text-xs flex-1"><SelectValue /></SelectTrigger>
                            <SelectContent>{VIS_OPERATORS.map(op => <SelectItem key={op.value} value={op.value}>{op.label}</SelectItem>)}</SelectContent>
                          </Select>
                          {(group.conditions.length > 1 || rs.groups.length > 1) && (
                            <button type="button" onClick={() => removeCond(gi, ci)} className="text-slate-300 hover:text-red-400"><X size={13} /></button>
                          )}
                        </div>
                      </div>
                    </div>
                    {!NO_VAL_OPS.has(cond.operator) && (
                      <Input value={cond.value || ""} onChange={e => setCond(gi, ci, { value: e.target.value })}
                        placeholder="e.g. yes, UK, premium" className="h-7 text-xs" />
                    )}
                  </div>
                ))}
                {group.conditions.length < MAX_CONDS && (
                  <button type="button" onClick={() => addCond(gi)}
                    className="flex items-center gap-1 text-[11px] text-blue-500 hover:text-blue-700 font-medium mt-1">
                    <Plus size={11} /> Add condition
                  </button>
                )}
              </div>
            </div>
          ))}
          {rs.groups.length < MAX_GROUPS && (
            <button type="button" onClick={addGroup}
              className="flex items-center gap-1.5 text-[11px] text-indigo-500 hover:text-indigo-700 font-medium border border-dashed border-indigo-200 rounded-md px-2.5 py-1.5 w-full justify-center hover:bg-indigo-50/50">
              <Plus size={11} /> Add group
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Address sub-field config types ────────────────────────────────────────────
export interface AddressSubField {
  enabled: boolean;
  required: boolean;
}

export interface AddressConfig {
  line1: AddressSubField;
  line2: AddressSubField;
  city: AddressSubField;
  state: AddressSubField;
  postal: AddressSubField;
  country: AddressSubField;
}

export const DEFAULT_ADDRESS_CONFIG: AddressConfig = {
  line1:   { enabled: true, required: true  },
  line2:   { enabled: true, required: false },
  city:    { enabled: true, required: true  },
  state:   { enabled: true, required: false },
  postal:  { enabled: true, required: true  },
  country: { enabled: true, required: true  },
};

export function getAddressConfig(field: FormField): AddressConfig {
  if (!field.address_config) return DEFAULT_ADDRESS_CONFIG;
  // Merge with defaults so any missing sub-field falls back gracefully
  return {
    line1:   { ...DEFAULT_ADDRESS_CONFIG.line1,   ...(field.address_config.line1   ?? {}) },
    line2:   { ...DEFAULT_ADDRESS_CONFIG.line2,   ...(field.address_config.line2   ?? {}) },
    city:    { ...DEFAULT_ADDRESS_CONFIG.city,    ...(field.address_config.city    ?? {}) },
    state:   { ...DEFAULT_ADDRESS_CONFIG.state,   ...(field.address_config.state   ?? {}) },
    postal:  { ...DEFAULT_ADDRESS_CONFIG.postal,  ...(field.address_config.postal  ?? {}) },
    country: { ...DEFAULT_ADDRESS_CONFIG.country, ...(field.address_config.country ?? {}) },
  };
}

// ── FormField interface ────────────────────────────────────────────────────────
export interface FormField {
  id: string;
  key: string;
  label: string;
  type: FieldType;
  required: boolean;
  placeholder: string;
  options: string[];
  locked: boolean;
  enabled: boolean;
  order: number;
  max_length?: number;
  max_file_size_mb?: number;   // file type
  date_format?: string;        // date type: "YYYY-MM-DD" | "DD/MM/YYYY" | "MM/DD/YYYY"
  min_value?: number;          // number type
  max_value?: number;          // number type
  address_config?: AddressConfig;
  terms_text?: string;         // terms_conditions type: the terms body text
  helper_text?: string;        // hint shown below the input
  tooltip_text?: string;       // ⓘ icon tooltip on hover
  show_when?: VisibilityRuleSet | null; // field-level dynamic visibility
}

export type FieldType = "text" | "email" | "tel" | "number" | "date" | "textarea" | "select" | "checkbox" | "file" | "password" | "address" | "terms_conditions" | "signature";

// Fields that must always be visible — hide/show toggle is suppressed for these
const ALWAYS_VISIBLE_KEYS = new Set(["org_name", "email", "admin_email", "password", "admin_password", "full_name", "admin_name"]);

const FIELD_TYPES: { value: FieldType; label: string }[] = [
  { value: "text",            label: "Text" },
  { value: "email",           label: "Email" },
  { value: "tel",             label: "Phone" },
  { value: "number",          label: "Number" },
  { value: "date",            label: "Date" },
  { value: "textarea",        label: "Textarea" },
  { value: "select",          label: "Dropdown" },
  { value: "checkbox",        label: "Checkbox" },
  { value: "file",            label: "File Upload" },
  { value: "password",        label: "Password" },
  { value: "address",         label: "Address Block" },
  { value: "terms_conditions", label: "Terms & Conditions" },
];

const ADDRESS_SUB_LABELS: { key: keyof AddressConfig; label: string }[] = [
  { key: "line1",   label: "Line 1" },
  { key: "line2",   label: "Line 2" },
  { key: "city",    label: "City" },
  { key: "state",   label: "State / Province" },
  { key: "postal",  label: "Postal Code" },
  { key: "country", label: "Country" },
];

function slugify(str: string): string {
  return str.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

function makeId(): string {
  return "f_" + Math.random().toString(36).slice(2, 8);
}

export function parseSchema(jsonStr: string): FormField[] {
  try {
    const parsed = JSON.parse(jsonStr);
    if (Array.isArray(parsed)) return parsed;
  } catch {}
  return [];
}

interface Props {
  value: string;
  onChange: (json: string) => void;
  title?: string;
  disableAddDelete?: boolean;
}

export default function FormSchemaBuilder({ value, onChange, title, disableAddDelete }: Props) {
  const [fields, setFields] = useState<FormField[]>(() =>
    parseSchema(value).sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
  );
  const [editingId, setEditingId] = useState<string | null>(null);

  const commit = (updated: FormField[]) => {
    const reordered = updated.map((f, i) => ({ ...f, order: i }));
    setFields(reordered);
    onChange(JSON.stringify(reordered));
  };

  const toggle = (id: string, key: keyof FormField, val: any) => {
    commit(fields.map(f => f.id === id ? { ...f, [key]: val } : f));
  };

  const move = (id: string, dir: -1 | 1) => {
    const idx = fields.findIndex(f => f.id === id);
    if (idx < 0) return;
    const next = idx + dir;
    if (next < 0 || next >= fields.length) return;
    const arr = [...fields];
    [arr[idx], arr[next]] = [arr[next], arr[idx]];
    commit(arr);
  };

  const remove = (id: string) => {
    let updated = fields.filter(f => f.id !== id);
    // If removing a TC field, also remove the companion signature
    const removed = fields.find(f => f.id === id);
    if (removed?.type === "terms_conditions") {
      updated = updated.filter(f => f.type !== "signature");
    }
    commit(updated);
    if (editingId === id) setEditingId(null);
  };

  const addField = () => {
    const id = makeId();
    const newField: FormField = {
      id, key: "new_field", label: "New Field", type: "text",
      required: false, placeholder: "", options: [],
      locked: false, enabled: true, order: fields.length,
    };
    commit([...fields, newField]);
    setEditingId(id);
  };

  const updateField = (id: string, patch: Partial<FormField>) => {
    commit(fields.map(f => {
      if (f.id !== id) return f;
      const updated = { ...f, ...patch };
      if (patch.label !== undefined && !f.locked) {
        updated.key = slugify(patch.label) || f.key;
      }
      // When switching to address type, add default config if not already set
      if (patch.type === "address" && !updated.address_config) {
        updated.address_config = { ...DEFAULT_ADDRESS_CONFIG };
      }
      return updated;
    }));
  };

  // When a terms_conditions field is added, auto-add a locked signature field after it
  const addTCWithSignature = (tcId: string, currentFields: FormField[]) => {
    const hasSig = currentFields.some(f => f.type === "signature");
    if (hasSig) return currentFields;
    const sigField: FormField = {
      id: makeId(), key: "signature", label: "Signature",
      type: "signature", required: true, placeholder: "",
      options: [], locked: true, enabled: true, order: currentFields.length,
    };
    const idx = currentFields.findIndex(f => f.id === tcId);
    const arr = [...currentFields];
    arr.splice(idx + 1, 0, sigField);
    return arr;
  };

  const handleTypeChange = (id: string, newType: FieldType) => {
    let updated = fields.map(f => {
      if (f.id !== id) return f;
      return { ...f, type: newType, options: [], key: newType === "terms_conditions" ? "terms_conditions" : f.key };
    });
    if (newType === "terms_conditions") {
      // Remove any existing signature field first, then re-add after TC
      updated = updated.filter(f => f.type !== "signature" || f.id === id);
      updated = addTCWithSignature(id, updated);
    }
    commit(updated);
  };

  const updateAddressSubField = (id: string, subKey: keyof AddressConfig, patch: Partial<AddressSubField>) => {
    commit(fields.map(f => {
      if (f.id !== id) return f;
      const cfg = getAddressConfig(f);
      return {
        ...f,
        address_config: {
          ...cfg,
          [subKey]: { ...cfg[subKey], ...patch },
        },
      };
    }));
  };

  return (
    <div data-testid="form-schema-builder">
      {title && <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">{title}</h4>}
      <div className="space-y-1.5">
        {fields.map((field, idx) => (
          <div key={field.id} className="border border-slate-200 rounded-lg bg-white overflow-hidden">
            {/* Field header row */}
            <div className="flex items-center gap-2 px-3 py-2">
              <GripVertical size={14} className="text-slate-300 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium text-slate-800 truncate">{field.label}</span>
                  {field.locked && <Lock size={10} className="text-amber-500 shrink-0" />}
                  <span className="text-[10px] text-slate-400 bg-slate-50 border border-slate-200 px-1.5 rounded font-mono">{field.type}</span>
                  {field.required && <span className="text-[10px] text-red-500">required</span>}
                  {field.show_when && <span title="Has visibility rule"><Eye size={10} className="text-blue-400 shrink-0" /></span>}
                  {field.locked && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${field.enabled ? "text-emerald-700 bg-emerald-50" : "text-slate-400 bg-slate-100"}`}>
                      {field.enabled ? "shown" : "hidden"}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 font-mono">{field.key}</p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {/* Hide/Show only for non-locked fields — locked fields are always shown */}
                {!field.locked && !ALWAYS_VISIBLE_KEYS.has(field.key) && (
                  <button
                    type="button"
                    onClick={() => toggle(field.id, "enabled", !field.enabled)}
                    className={`text-xs px-2 py-1 rounded transition-colors ${field.enabled ? "bg-slate-100 text-slate-600 hover:bg-slate-200" : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"}`}
                    data-testid={`field-toggle-${field.id}`}
                  >
                    {field.enabled ? "Hide" : "Show"}
                  </button>
                )}
                {/* Move up/down — locked fields cannot be reordered */}
                {!field.locked && (
                  <>
                    <button type="button" onClick={() => move(field.id, -1)} disabled={idx === 0} className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30">
                      <ChevronUp size={14} />
                    </button>
                    <button type="button" onClick={() => move(field.id, 1)} disabled={idx === fields.length - 1} className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30">
                      <ChevronDown size={14} />
                    </button>
                  </>
                )}
                <button type="button" onClick={() => setEditingId(editingId === field.id ? null : field.id)} className={`p-1 rounded transition-colors ${editingId === field.id ? "text-blue-600 bg-blue-50" : "text-slate-400 hover:text-slate-600"}`}>
                  <Settings2 size={14} />
                </button>
                {!field.locked && !disableAddDelete && (
                  <button type="button" onClick={() => remove(field.id)} className="p-1 text-slate-400 hover:text-red-500">
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>

            {/* Inline edit panel */}
            {editingId === field.id && (
              <div className="border-t border-slate-100 bg-slate-50 p-3 grid grid-cols-2 gap-3">
                {/* Label + Type */}
                <div>
                  <label className="text-[11px] text-slate-500 font-medium">
                    Label{field.key === "base_currency" && <span className="ml-1 text-[10px] text-slate-400">(non-editable)</span>}
                  </label>
                  <Input
                    value={field.label}
                    onChange={e => updateField(field.id, { label: e.target.value })}
                    className={`mt-0.5 h-7 text-xs ${field.key === "base_currency" ? "bg-slate-100 cursor-not-allowed text-slate-400" : ""}`}
                    maxLength={50}
                    readOnly={field.key === "base_currency"}
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-500 font-medium">Field type</label>
                  {field.locked ? (
                    <div className="mt-0.5 h-7 text-xs px-2 flex items-center bg-slate-100 border border-slate-200 rounded-md text-slate-400 cursor-not-allowed">
                      {FIELD_TYPES.find(t => t.value === field.type)?.label || field.type}
                      <Lock size={10} className="ml-1.5 text-amber-400" />
                    </div>
                  ) : (
                    <Select value={field.type} onValueChange={v => handleTypeChange(field.id, v as FieldType)}>
                      <SelectTrigger className="mt-0.5 h-7 text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {FIELD_TYPES.filter(t => t.value !== "signature").map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  )}
                  {(field.type === "email" || field.type === "tel") && (
                    <p className="mt-1 text-[10px] text-blue-600 bg-blue-50 border border-blue-100 rounded px-1.5 py-0.5">
                      Auto-validates format on submit
                    </p>
                  )}
                </div>

                {/* Address sub-field config (only for address type) */}
                {field.type === "terms_conditions" ? (
                  <div className="col-span-2">
                    <label className="text-[11px] text-slate-500 font-medium block mb-1">Terms & Conditions Text</label>
                    <Textarea
                      value={field.terms_text || ""}
                      onChange={e => updateField(field.id, { terms_text: e.target.value })}
                      rows={6}
                      maxLength={10000}
                      className="mt-0.5 text-xs"
                      placeholder="Enter the full terms and conditions text here. The customer must read and sign below."
                      data-testid={`field-terms-text-${field.id}`}
                    />
                    <p className={`text-[10px] mt-0.5 text-right ${(field.terms_text || "").length > 9500 ? "text-red-500" : (field.terms_text || "").length > 8000 ? "text-amber-500" : "text-slate-400"}`}>
                      {(field.terms_text || "").length.toLocaleString()}/10,000
                    </p>
                    <p className="text-[10px] text-amber-600 bg-amber-50 border border-amber-100 rounded px-1.5 py-0.5 mt-1.5">
                      A signature field is automatically appended below this field and cannot be removed separately.
                    </p>
                  </div>
                ) : field.type === "signature" ? (
                  <div className="col-span-2">
                    <p className="text-[11px] text-slate-500 bg-amber-50 border border-amber-100 rounded px-2 py-1.5">
                      This signature field is automatically managed by the Terms &amp; Conditions field above. It requires a drawn signature and typed name.
                    </p>
                  </div>
                ) : field.type === "address" ? (                  <div className="col-span-2">
                    <label className="text-[11px] text-slate-500 font-medium block mb-2">Sub-field Configuration</label>
                    <div className="rounded border border-slate-200 overflow-hidden">
                      <div className="grid grid-cols-3 gap-0 bg-slate-100 px-3 py-1.5">
                        <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Field</span>
                        <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide text-center">Enabled</span>
                        <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide text-center">Required</span>
                      </div>
                      {ADDRESS_SUB_LABELS.map(({ key: subKey, label: subLabel }) => {
                        const cfg = getAddressConfig(field)[subKey];
                        return (
                          <div key={subKey} className="grid grid-cols-3 gap-0 px-3 py-2 border-t border-slate-100 items-center">
                            <span className="text-xs text-slate-700">{subLabel}</span>
                            <div className="flex justify-center">
                              <input
                                type="checkbox"
                                checked={cfg.enabled}
                                onChange={e => updateAddressSubField(field.id, subKey, { enabled: e.target.checked, required: e.target.checked ? cfg.required : false })}
                                className="w-3.5 h-3.5 cursor-pointer"
                                data-testid={`addr-subfield-enabled-${field.id}-${subKey}`}
                              />
                            </div>
                            <div className="flex justify-center">
                              <input
                                type="checkbox"
                                checked={cfg.required}
                                disabled={!cfg.enabled}
                                onChange={e => updateAddressSubField(field.id, subKey, { required: e.target.checked })}
                                className="w-3.5 h-3.5 cursor-pointer disabled:opacity-30"
                                data-testid={`addr-subfield-required-${field.id}-${subKey}`}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <p className="text-[10px] text-slate-400 mt-1.5">Country and Province/State options are dynamically pulled from your <strong>Taxes</strong> configuration.</p>
                  </div>
                ) : (
                  <>
                    {/* Standard placeholder + required for non-address types */}
                    <div>
                      <label className="text-[11px] text-slate-500 font-medium">Placeholder</label>
                      <Input value={field.placeholder} onChange={e => updateField(field.id, { placeholder: e.target.value })} maxLength={200} className="mt-0.5 h-7 text-xs" />
                    </div>
                    <div className="flex items-end gap-4 pb-1">
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input type="checkbox" checked={field.required} onChange={e => updateField(field.id, { required: e.target.checked })} className="w-3.5 h-3.5" data-testid={`field-required-${field.id}`} />
                        <span className="text-xs text-slate-600">Required</span>
                      </label>
                      {!ALWAYS_VISIBLE_KEYS.has(field.key) && !field.locked && (
                        <label className="flex items-center gap-1.5 cursor-pointer">
                          <input type="checkbox" checked={field.enabled !== false} onChange={e => updateField(field.id, { enabled: e.target.checked })} className="w-3.5 h-3.5" data-testid={`field-enabled-${field.id}`} />
                          <span className="text-xs text-slate-600">Visible</span>
                        </label>
                      )}
                    </div>
                    {/* Max length — only for text/email/tel/textarea fields */}
                    {(["text", "email", "tel", "textarea", "password"].includes(field.type)) && (
                      <div>
                        <label className="text-[11px] text-slate-500 font-medium">Max characters <span className="text-slate-400">(optional)</span></label>
                        <Input
                          type="number"
                          min={1}
                          max={10000}
                          value={field.max_length ?? ""}
                          onChange={e => updateField(field.id, { max_length: e.target.value ? Number(e.target.value) : undefined })}
                          placeholder="No limit"
                          className="mt-0.5 h-7 text-xs"
                          data-testid={`field-maxlength-${field.id}`}
                        />
                      </div>
                    )}
                    {/* Number min/max */}
                    {field.type === "number" && (
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[11px] text-slate-500 font-medium">Min value</label>
                          <Input
                            type="number"
                            value={field.min_value ?? ""}
                            onChange={e => updateField(field.id, { min_value: e.target.value ? Number(e.target.value) : undefined })}
                            placeholder="None"
                            className="mt-0.5 h-7 text-xs"
                            data-testid={`field-minvalue-${field.id}`}
                          />
                        </div>
                        <div>
                          <label className="text-[11px] text-slate-500 font-medium">Max value</label>
                          <Input
                            type="number"
                            value={field.max_value ?? ""}
                            onChange={e => updateField(field.id, { max_value: e.target.value ? Number(e.target.value) : undefined })}
                            placeholder="None"
                            className="mt-0.5 h-7 text-xs"
                            data-testid={`field-maxvalue-${field.id}`}
                          />
                        </div>
                      </div>
                    )}
                    {/* Date format */}
                    {field.type === "date" && (
                      <div>
                        <label className="text-[11px] text-slate-500 font-medium">Date format</label>
                        <select
                          value={field.date_format || "YYYY-MM-DD"}
                          onChange={e => updateField(field.id, { date_format: e.target.value })}
                          className="mt-0.5 h-7 text-xs w-full rounded-md border border-input bg-background px-2"
                          data-testid={`field-dateformat-${field.id}`}
                        >
                          <option value="YYYY-MM-DD">YYYY-MM-DD (ISO)</option>
                          <option value="DD/MM/YYYY">DD/MM/YYYY (UK / EU)</option>
                          <option value="MM/DD/YYYY">MM/DD/YYYY (US)</option>
                          <option value="DD-MM-YYYY">DD-MM-YYYY</option>
                          <option value="MM-DD-YYYY">MM-DD-YYYY</option>
                        </select>
                      </div>
                    )}
                    {/* File upload — max size */}
                    {field.type === "file" && (
                      <div>
                        <label className="text-[11px] text-slate-500 font-medium">Max file size <span className="text-slate-400">(MB, optional)</span></label>
                        <Input
                          type="number"
                          min={1}
                          max={500}
                          value={field.max_file_size_mb ?? ""}
                          onChange={e => updateField(field.id, { max_file_size_mb: e.target.value ? Number(e.target.value) : undefined })}
                          placeholder="No limit"
                          className="mt-0.5 h-7 text-xs"
                          data-testid={`field-maxfilesize-${field.id}`}
                        />
                      </div>
                    )}
                      {field.type === "select" && (
                      <div className="col-span-2">
                        <label className="text-[11px] text-slate-500 font-medium">Options (one per line, format: Label|value)</label>
                        <Textarea
                          value={
                            Array.isArray(field.options)
                              ? field.options.join("\n")
                              : (field.options || "")
                          }
                          onChange={e =>
                            // Keep empty lines while typing so cursor/newlines are preserved
                            updateField(field.id, { options: e.target.value.split("\n") })
                          }
                          onBlur={e =>
                            // Strip blank lines only when the user leaves the field
                            updateField(field.id, { options: e.target.value.split("\n").filter(s => s.trim()) })
                          }
                          rows={4}
                          className="mt-0.5 text-xs font-mono"
                          placeholder={"Option One|opt_1\nOption Two|opt_2\nOption Three|opt_3"}
                        />
                        <p className="text-[10px] text-slate-400 mt-1">Press Enter to add a new option. Use Label|value format to set separate display labels and values.</p>
                      </div>
                    )}
                    {/* Helper text + Tooltip */}
                    <div className="col-span-2 grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-[11px] text-slate-500 font-medium">Helper text <span className="text-slate-400 font-normal">(shown below field)</span></label>
                        <Input value={field.helper_text || ""} onChange={e => updateField(field.id, { helper_text: e.target.value })} maxLength={500} className="mt-0.5 h-7 text-xs" placeholder="e.g. Enter your date of birth" data-testid={`field-helper-${field.id}`} />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-500 font-medium flex items-center gap-1"><Info size={10} /> Tooltip <span className="text-slate-400 font-normal">(hover ⓘ)</span></label>
                        <Input value={field.tooltip_text || ""} onChange={e => updateField(field.id, { tooltip_text: e.target.value })} maxLength={500} className="mt-0.5 h-7 text-xs" placeholder="e.g. Must match your government ID" data-testid={`field-tooltip-${field.id}`} />
                      </div>
                    </div>
                    {/* Visibility rule — not for locked/signature fields */}
                    {!field.locked && (field.type as string) !== "signature" && (
                      <VisibilityRuleEditor
                        rule={field.show_when}
                        onChange={r => updateField(field.id, { show_when: r })}
                        otherFields={fields.filter(f => f.id !== field.id)}
                      />
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {!disableAddDelete && (
        <button
          type="button"
          onClick={addField}
          className="mt-2 flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 font-medium px-2 py-1.5 rounded hover:bg-blue-50 transition-colors"
          data-testid="add-form-field-btn"
        >
          <Plus size={13} /> Add field
        </button>
      )}
    </div>
  );
}
