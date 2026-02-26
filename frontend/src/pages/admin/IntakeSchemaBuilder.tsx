import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  X, Plus, ChevronUp, ChevronDown, ChevronRight,
  Hash, AlignLeft, AlignJustify, List, CheckSquare, GripVertical, ToggleLeft,
  Layers, Eye, AlertCircle, Calendar, Paperclip, Zap, FileText, Info,
} from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// ── Types ──────────────────────────────────────────────────────────────────────
export type QType =
  | "dropdown" | "multiselect" | "number" | "boolean"
  | "single_line" | "multi_line" | "date" | "file"
  | "formula" | "html_block";

export interface IntakeOption { label: string; value: string; price_value: number; }
export interface PricingTier { from: number; to: number | null; price_per_unit: number; }
export interface VisibilityConditionRow {
  depends_on: string;
  operator: "equals" | "not_equals" | "greater_than" | "less_than" | "contains" | "not_contains" | "not_empty" | "empty";
  value: string;
}

/** One group: conditions joined by group-level AND/OR */
export interface VisibilityGroup {
  logic: "AND" | "OR";
  conditions: VisibilityConditionRow[];
}

/** New grouped rule set (top_logic joins groups) */
export interface VisibilityRuleSet {
  top_logic: "AND" | "OR";
  groups: VisibilityGroup[];
}

/** Legacy single-rule format kept for backward compat */
export interface VisibilityRule {
  depends_on: string;
  operator: "equals" | "not_equals" | "greater_than" | "less_than" | "contains" | "not_empty";
  value: string;
}

export interface IntakeQuestion {
  key: string;
  label: string;
  helper_text: string;
  tooltip_text?: string;
  required: boolean;
  enabled: boolean;
  order: number;
  step_group: number;
  type: QType;
  // Dropdown / Multiselect
  affects_price?: boolean;
  price_mode?: "add" | "multiply";
  options?: IntakeOption[];
  // Number — flat or tiered
  price_per_unit?: number;
  pricing_mode?: "flat" | "tiered";
  tiers?: PricingTier[];
  min?: number;
  max?: number;
  step?: number;
  default_value?: number;
  // Boolean
  price_for_yes?: number;
  price_for_no?: number;
  // Formula
  formula_expression?: string;
  // Date
  date_format?: "date" | "date_range";
  // File
  accept?: string;
  max_size_mb?: number;
  // HTML block
  content?: string;
  // Visibility — supports both new VisibilityRuleSet and legacy VisibilityRule
  visibility_rule?: VisibilityRuleSet | VisibilityRule | null;
}

export interface IntakeSchemaJson {
  version: number;
  updated_at?: string;
  updated_by?: string;
  questions: IntakeQuestion[];
  price_floor?: number | null;
  price_ceiling?: number | null;
}

export const EMPTY_INTAKE_SCHEMA: IntakeSchemaJson = { version: 2, questions: [] };

// ── Helpers ────────────────────────────────────────────────────────────────────
const labelToKey = (s: string) =>
  s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40);

const QUESTION_TYPES: { type: QType; label: string; icon: React.ReactNode; desc: string; group: string }[] = [
  { type: "dropdown",    label: "Dropdown",      icon: <List size={14} />,         desc: "Single select from options",           group: "Choice" },
  { type: "multiselect", label: "Multi-select",   icon: <CheckSquare size={14} />,  desc: "Multiple options selectable",          group: "Choice" },
  { type: "boolean",     label: "Yes / No",       icon: <ToggleLeft size={14} />,   desc: "Simple yes or no question",            group: "Choice" },
  { type: "number",      label: "Number",         icon: <Hash size={14} />,         desc: "Numeric — flat or tiered pricing",     group: "Input" },
  { type: "single_line", label: "Short text",     icon: <AlignLeft size={14} />,    desc: "One-line text answer",                 group: "Input" },
  { type: "multi_line",  label: "Long text",      icon: <AlignJustify size={14} />, desc: "Paragraph text answer",               group: "Input" },
  { type: "date",        label: "Date",           icon: <Calendar size={14} />,     desc: "Date or date range picker",            group: "Input" },
  { type: "file",        label: "File upload",    icon: <Paperclip size={14} />,    desc: "Customer uploads a document or image", group: "Input" },
  { type: "formula",     label: "Formula",        icon: <Zap size={14} />,          desc: "Calculated from other field values",   group: "Pricing" },
  { type: "html_block",  label: "Content block",  icon: <FileText size={14} />,     desc: "Section header or instructions text",  group: "Layout" },
];
const TYPE_LABELS: Record<QType, string> = {
  dropdown: "Dropdown", multiselect: "Multi-select", number: "Number", boolean: "Yes/No",
  single_line: "Short text", multi_line: "Long text", date: "Date", file: "File",
  formula: "Formula", html_block: "Content",
};

const emptyQuestion = (type: QType, order: number): IntakeQuestion => ({
  key: type === "html_block" ? `block_${order}` : "",
  label: "", helper_text: "", tooltip_text: "", required: false, enabled: true, order,
  step_group: 0, type,
  ...(type === "dropdown" || type === "multiselect" ? { affects_price: false, price_mode: "add", options: [] } : {}),
  ...(type === "number" ? { price_per_unit: 0, pricing_mode: "flat", tiers: [], min: 0, max: 1000, step: 1 } : {}),
  ...(type === "boolean" ? { affects_price: false, price_for_yes: 0, price_for_no: 0 } : {}),
  ...(type === "formula" ? { formula_expression: "" } : {}),
  ...(type === "date" ? { date_format: "date" } : {}),
  ...(type === "file" ? { accept: ".pdf,.docx,.jpg,.png", max_size_mb: 10 } : {}),
  ...(type === "html_block" ? { content: "" } : {}),
});

const hasOptions = (t: QType) => t === "dropdown" || t === "multiselect";

// ── Sub-editors ────────────────────────────────────────────────────────────────

function OptionsEditor({ options, onChange, affects_price }: {
  options: IntakeOption[]; onChange: (v: IntakeOption[]) => void; affects_price?: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="label-xs">Options</span>
        {affects_price && <span className="text-[10px] text-slate-400">Price adj. (£)</span>}
      </div>
      {options.map((opt, i) => (
        <div key={i} className="flex gap-2 items-center">
          <Input value={opt.label} onChange={e => {
            const n = [...options]; n[i] = { ...n[i], label: e.target.value, value: labelToKey(e.target.value) }; onChange(n);
          }} placeholder="Option label" className="h-8 text-xs flex-1" />
          {affects_price && (
            <Input type="number" value={opt.price_value ?? 0} onChange={e => {
              const n = [...options]; n[i] = { ...n[i], price_value: parseFloat(e.target.value) || 0 }; onChange(n);
            }} placeholder="0" className="h-8 text-xs w-20 font-mono" />
          )}
          <button type="button" onClick={() => onChange(options.filter((_, j) => j !== i))}
            className="text-slate-400 hover:text-red-500 transition-colors"><X size={13} /></button>
        </div>
      ))}
      <Button type="button" variant="outline" size="sm"
        onClick={() => onChange([...options, { label: "", value: "", price_value: 0 }])}
        className="h-7 text-xs px-2 text-slate-500 hover:text-slate-700">
        <Plus size={11} className="mr-1" /> Add option
      </Button>
    </div>
  );
}

function TierEditor({ tiers, onChange }: { tiers: PricingTier[]; onChange: (t: PricingTier[]) => void }) {
  const addTier = () => {
    const lastTo = tiers.length > 0 ? (tiers[tiers.length - 1].to ?? 0) : 0;
    onChange([...tiers, { from: lastTo, to: null, price_per_unit: 0 }]);
  };
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="label-xs">Pricing tiers</span>
        <button type="button" onClick={addTier}
          className="flex items-center gap-1 text-xs text-[#1e40af] hover:text-blue-700 font-medium transition-colors">
          <Plus size={11} /> Add tier
        </button>
      </div>
      {tiers.length === 0 && <p className="text-xs text-slate-400 italic">No tiers yet</p>}
      {tiers.length > 0 && (
        <>
          <div className="grid grid-cols-[1fr_1fr_1fr_24px] gap-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            <span>From</span><span>To (∞=blank)</span><span>£/unit</span><span />
          </div>
          {tiers.map((tier, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_1fr_24px] gap-2 items-center">
              <Input type="number" value={tier.from ?? 0} onChange={e => {
                const n = [...tiers]; n[i] = { ...n[i], from: parseFloat(e.target.value) || 0 }; onChange(n);
              }} className="h-8 text-xs font-mono" />
              <Input type="number" value={tier.to ?? ""} onChange={e => {
                const n = [...tiers]; n[i] = { ...n[i], to: e.target.value === "" ? null : parseFloat(e.target.value) }; onChange(n);
              }} className="h-8 text-xs font-mono" placeholder="∞" />
              <Input type="number" value={tier.price_per_unit ?? 0} onChange={e => {
                const n = [...tiers]; n[i] = { ...n[i], price_per_unit: parseFloat(e.target.value) || 0 }; onChange(n);
              }} className="h-8 text-xs font-mono" />
              <button type="button" onClick={() => onChange(tiers.filter((_, j) => j !== i))}
                className="text-slate-400 hover:text-red-500 transition-colors"><X size={12} /></button>
            </div>
          ))}
          <p className="text-[10px] text-slate-400">Progressive pricing: first N units at rate 1, next N at rate 2, etc.</p>
        </>
      )}
    </div>
  );
}

const OPERATORS = [
  { value: "equals",       label: "= equals" },
  { value: "not_equals",   label: "≠ not equals" },
  { value: "greater_than", label: "> greater than" },
  { value: "less_than",    label: "< less than" },
  { value: "contains",     label: "contains" },
  { value: "not_contains", label: "does not contain" },
  { value: "not_empty",    label: "is not empty" },
  { value: "empty",        label: "is empty / null" },
];

const NO_VALUE_OPS = new Set(["not_empty", "empty"]);
const MAX_CONDS_PER_GROUP = 4;
const MAX_GROUPS = 3;
const DEFAULT_COND = (): VisibilityConditionRow => ({ depends_on: "", operator: "equals", value: "" });
const DEFAULT_GROUP = (): VisibilityGroup => ({ logic: "AND", conditions: [DEFAULT_COND()] });

// ── Mini toggle ────────────────────────────────────────────────────────────────
const MiniToggle = ({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) => (
  <label className="flex items-center gap-2 cursor-pointer select-none group">
    <span className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors ${checked ? "bg-[#0f172a]" : "bg-slate-200 group-hover:bg-slate-300"}`}>
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} className="sr-only" />
      <span className={`inline-block h-3 w-3 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-3.5" : "translate-x-0.5"}`} />
    </span>
    <span className="text-xs text-slate-600">{label}</span>
  </label>
);

// ── Visibility summary ─────────────────────────────────────────────────────────
function getVisibilitySummary(rule: any): string {
  try {
    const rs = normaliseRule(rule);
    const totalConds = rs.groups.reduce((s, g) => s + g.conditions.length, 0);
    if (!totalConds) return "";
    const first = rs.groups[0]?.conditions[0];
    if (!first?.depends_on) return `${totalConds} condition${totalConds !== 1 ? "s" : ""}`;
    const opMap: Record<string, string> = { equals: "=", not_equals: "≠", greater_than: ">", less_than: "<", contains: "contains", not_contains: "!contains", not_empty: "≠ empty", empty: "= empty" };
    const op = opMap[first.operator] ?? first.operator;
    const val = NO_VALUE_OPS.has(first.operator) ? "" : ` "${first.value}"`;
    const line = `${first.depends_on} ${op}${val}`;
    return totalConds > 1 ? `${line} +${totalConds - 1} more` : line;
  } catch { return ""; }
}

/** Normalise any saved rule (legacy or flat or grouped) into the current grouped VisibilityRuleSet */
function normaliseRule(raw: any): VisibilityRuleSet {
  if (!raw) return { top_logic: "AND", groups: [DEFAULT_GROUP()] };
  // Already grouped format
  if (raw.groups && Array.isArray(raw.groups)) return raw as VisibilityRuleSet;
  // Old flat format: { logic, conditions }
  if (raw.conditions && Array.isArray(raw.conditions))
    return { top_logic: "AND", groups: [{ logic: raw.logic || "AND", conditions: raw.conditions }] };
  // Legacy single-rule: { depends_on, operator, value }
  return { top_logic: "AND", groups: [{ logic: "AND", conditions: [{ depends_on: raw.depends_on ?? "", operator: raw.operator ?? "equals", value: raw.value ?? "" }] }] };
}

// ── Logic pill (AND / OR toggle) ───────────────────────────────────────────────
function LogicPill({ value, onChange, small }: { value: "AND" | "OR"; onChange: (v: "AND" | "OR") => void; small?: boolean }) {
  const base = small ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-0.5 text-[10px]";
  return (
    <div className="flex rounded overflow-hidden border border-blue-200">
      {(["AND", "OR"] as const).map(l => (
        <button key={l} type="button" onClick={() => onChange(l)}
          className={`${base} font-bold transition-colors ${value === l ? "bg-blue-600 text-white" : "bg-white text-blue-500 hover:bg-blue-50"}`}>
          {l}
        </button>
      ))}
    </div>
  );
}

function VisibilityRuleEditor({ rule, onChange, otherQuestions }: {
  rule: VisibilityRuleSet | VisibilityRule | null | undefined;
  onChange: (r: VisibilityRuleSet | null) => void;
  otherQuestions: IntakeQuestion[];
}) {
  const isOn = !!rule;
  const ruleSet: VisibilityRuleSet = isOn ? normaliseRule(rule) : { top_logic: "AND", groups: [DEFAULT_GROUP()] };

  const toggle = (checked: boolean) => onChange(checked ? ruleSet : null);

  const setTopLogic = (tl: "AND" | "OR") => onChange({ ...ruleSet, top_logic: tl });
  const setGroupLogic = (gi: number, logic: "AND" | "OR") =>
    onChange({ ...ruleSet, groups: ruleSet.groups.map((g, i) => i === gi ? { ...g, logic } : g) });

  const setCond = (gi: number, ci: number, patch: Partial<VisibilityConditionRow>) =>
    onChange({
      ...ruleSet,
      groups: ruleSet.groups.map((g, i) => i !== gi ? g : {
        ...g, conditions: g.conditions.map((c, j) => j !== ci ? c : { ...c, ...patch }),
      }),
    });

  const addCond = (gi: number) => {
    const g = ruleSet.groups[gi];
    if (g.conditions.length >= MAX_CONDS_PER_GROUP) return;
    onChange({
      ...ruleSet,
      groups: ruleSet.groups.map((grp, i) => i !== gi ? grp : { ...grp, conditions: [...grp.conditions, DEFAULT_COND()] }),
    });
  };

  const removeCond = (gi: number, ci: number) => {
    const newGroups = ruleSet.groups
      .map((g, i) => i !== gi ? g : { ...g, conditions: g.conditions.filter((_, j) => j !== ci) })
      .filter(g => g.conditions.length > 0);
    onChange(newGroups.length ? { ...ruleSet, groups: newGroups } : null);
  };

  const addGroup = () => {
    if (ruleSet.groups.length >= MAX_GROUPS) return;
    onChange({ ...ruleSet, groups: [...ruleSet.groups, DEFAULT_GROUP()] });
  };

  const removeGroup = (gi: number) => {
    const newGroups = ruleSet.groups.filter((_, i) => i !== gi);
    onChange(newGroups.length ? { ...ruleSet, groups: newGroups } : null);
  };

  const eligibleQs = otherQuestions.filter(q => q.key && q.type !== "html_block");

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-1.5 label-xs cursor-pointer"><Eye size={11} /> Visibility rule</label>
        <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer select-none">
          <input type="checkbox" checked={isOn} onChange={e => toggle(e.target.checked)} className="w-3 h-3 rounded accent-[#0f172a]" />
          {isOn ? "On" : "Off"}
        </label>
      </div>

      {isOn && (
        <div className="space-y-2">
          <p className="text-[11px] text-blue-600 font-medium">Show this question only when:</p>

          {ruleSet.groups.map((group, gi) => (
            <div key={gi}>
              {/* Top-level connector between groups */}
              {gi > 0 && (
                <div className="flex items-center gap-2 my-2">
                  <div className="flex-1 border-t border-dashed border-slate-300" />
                  <LogicPill value={ruleSet.top_logic} onChange={setTopLogic} />
                  <div className="flex-1 border-t border-dashed border-slate-300" />
                </div>
              )}

              {/* Group card */}
              <div className="bg-blue-50/60 border border-blue-100 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-blue-500 uppercase tracking-wide">
                    {ruleSet.groups.length > 1 ? `Group ${gi + 1}` : "Conditions"}
                  </span>
                  <div className="flex items-center gap-2">
                    {group.conditions.length > 1 && (
                      <LogicPill value={group.logic} onChange={l => setGroupLogic(gi, l)} small />
                    )}
                    {ruleSet.groups.length > 1 && (
                      <button type="button" onClick={() => removeGroup(gi)} className="text-slate-300 hover:text-red-400 transition-colors ml-1">
                        <X size={12} />
                      </button>
                    )}
                  </div>
                </div>

                {group.conditions.map((cond, ci) => (
                  <div key={ci} className="space-y-1.5">
                    {ci > 0 && (
                      <div className="flex items-center gap-1.5 my-1">
                        <div className="flex-1 border-t border-blue-100" />
                        <span className="text-[9px] font-bold text-blue-400">{group.logic}</span>
                        <div className="flex-1 border-t border-blue-100" />
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[10px] text-slate-500 block mb-1">Question</label>
                        <Select value={cond.depends_on || ""} onValueChange={v => setCond(gi, ci, { depends_on: v })}>
                          <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Pick…" /></SelectTrigger>
                          <SelectContent>
                            {eligibleQs.map(q => (
                              <SelectItem key={q.key} value={q.key}>{q.label || q.key || "(untitled)"}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-500 block mb-1">Condition</label>
                        <div className="flex gap-1">
                          <Select value={cond.operator} onValueChange={v => setCond(gi, ci, { operator: v as any, value: NO_VALUE_OPS.has(v) ? "" : cond.value })}>
                            <SelectTrigger className="h-8 text-xs flex-1"><SelectValue /></SelectTrigger>
                            <SelectContent>{OPERATORS.map(op => <SelectItem key={op.value} value={op.value}>{op.label}</SelectItem>)}</SelectContent>
                          </Select>
                          {(group.conditions.length > 1 || ruleSet.groups.length > 1) && (
                            <button type="button" onClick={() => removeCond(gi, ci)} className="text-slate-300 hover:text-red-400 transition-colors">
                              <X size={13} />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                    {!NO_VALUE_OPS.has(cond.operator) && (
                      <Input value={cond.value || ""} onChange={e => setCond(gi, ci, { value: e.target.value })}
                        placeholder="e.g. yes, 5, premium" className="h-8 text-xs" />
                    )}
                  </div>
                ))}

                {group.conditions.length < MAX_CONDS_PER_GROUP && (
                  <button type="button" onClick={() => addCond(gi)}
                    className="flex items-center gap-1 text-[11px] text-blue-500 hover:text-blue-700 font-medium transition-colors mt-1">
                    <Plus size={11} /> Add condition
                  </button>
                )}
              </div>
            </div>
          ))}

          {ruleSet.groups.length < MAX_GROUPS && (
            <button type="button" onClick={addGroup}
              className="flex items-center gap-1.5 text-[11px] text-indigo-500 hover:text-indigo-700 font-medium transition-colors border border-dashed border-indigo-200 rounded-md px-2.5 py-1.5 w-full justify-center hover:bg-indigo-50/50">
              <Plus size={11} /> Add group
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Question Card ──────────────────────────────────────────────────────────────
function QuestionCard({ q, idx, total, allKeys, allQuestions, onChange, onRemove, onMove }: {
  q: IntakeQuestion; idx: number; total: number; allKeys: string[];
  allQuestions: IntakeQuestion[];
  onChange: (q: IntakeQuestion) => void; onRemove: () => void; onMove: (dir: -1 | 1) => void;
}) {
  const [open, setOpen] = useState(true);
  const isDuplicate = q.type !== "html_block" && q.key !== "" && allKeys.filter(k => k === q.key).length > 1;
  const typeInfo = QUESTION_TYPES.find(t => t.type === q.type)!;
  const otherQ = allQuestions.filter((_, i) => i !== idx);
  const isHtmlBlock = q.type === "html_block";

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className={`group bg-white border rounded-lg overflow-hidden transition-all shadow-sm ${
        isHtmlBlock ? "border-dashed border-blue-200 bg-blue-50/30" : "border-slate-200 hover:border-slate-300"
      }`}>
        {/* Header */}
        <CollapsibleTrigger asChild>
          <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-slate-50 select-none transition-colors">
            <GripVertical size={14} className="text-slate-300 shrink-0" />
            <span className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded shrink-0 ${
              isHtmlBlock ? "bg-blue-100 border border-blue-200 text-blue-600" : "bg-slate-100 border border-slate-200 text-slate-600"
            }`}>{typeInfo.icon}{TYPE_LABELS[q.type]}</span>
            <span className="text-sm font-medium text-slate-900 flex-1 truncate">
              {q.label || <span className="text-slate-400 font-normal italic">{isHtmlBlock ? "Untitled block" : "Untitled question"}</span>}
            </span>
            {q.visibility_rule && <Eye size={12} className="text-blue-400 shrink-0" />}
            {!q.enabled && <span className="text-[10px] text-slate-400 shrink-0">disabled</span>}
            <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
              <button type="button" onClick={e => { e.stopPropagation(); onMove(-1); }} disabled={idx === 0}
                className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-25 rounded"><ChevronUp size={13} /></button>
              <button type="button" onClick={e => { e.stopPropagation(); onMove(1); }} disabled={idx === total - 1}
                className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-25 rounded"><ChevronDown size={13} /></button>
              <button type="button" onClick={e => { e.stopPropagation(); onRemove(); }}
                className="p-1 text-slate-400 hover:text-red-500 rounded transition-colors"><X size={13} /></button>
            </div>
            <ChevronRight size={14} className={`text-slate-400 transition-transform shrink-0 ${open ? "rotate-90" : ""}`} />
          </div>
        </CollapsibleTrigger>

        {/* Body */}
        <CollapsibleContent>
          <div className="px-4 pb-4 pt-3 border-t border-slate-100 bg-slate-50/50 space-y-4">
            {/* HTML Block */}
            {isHtmlBlock ? (
              <>
                <div>
                  <label className="label-xs">Block title <span className="text-slate-400 font-normal normal-case tracking-normal">(optional heading)</span></label>
                  <Input value={q.label} onChange={e => onChange({ ...q, label: e.target.value })}
                    placeholder="Section heading" className="h-9 text-sm" />
                </div>
                <div>
                  <label className="label-xs">Content (HTML)</label>
                  <Textarea value={q.content || ""} onChange={e => onChange({ ...q, content: e.target.value })}
                    placeholder="<p>Instructions for this section...</p>"
                    rows={4} className="text-xs font-mono resize-y" />
                  <p className="text-[10px] text-slate-400 mt-1">HTML is rendered on the product page. In Wizard mode, this block starts a new step.</p>
                </div>
                <div>
                  <label className="label-xs">Step group <span className="text-slate-400 font-normal normal-case tracking-normal">(wizard layout)</span></label>
                  <Input type="number" value={q.step_group ?? 0}
                    onChange={e => onChange({ ...q, step_group: parseInt(e.target.value) || 0 })}
                    className="h-8 text-xs w-20 font-mono" min={0} />
                </div>
              </>
            ) : (
              <>
                {/* Label + Key */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label-xs">Label *</label>
                    <Input value={q.label}
                      onChange={e => onChange({ ...q, label: e.target.value, key: labelToKey(e.target.value) })}
                      placeholder="Question label" className="h-9 text-sm" />
                  </div>
                  <div>
                    <label className={`text-[11px] font-semibold uppercase tracking-wider block mb-1.5 ${isDuplicate ? "text-red-500" : "text-slate-400"}`}>
                      Key {isDuplicate && <span className="text-red-500">(duplicate!)</span>}
                    </label>
                    <div className={`h-9 flex items-center px-3 rounded-md border text-xs font-mono ${
                      isDuplicate ? "border-red-300 text-red-600 bg-red-50" : "border-slate-200 text-slate-500 bg-white"
                    }`}>{q.key || <span className="italic text-slate-300">auto</span>}</div>
                  </div>
                </div>

                {/* Helper + Tooltip */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label-xs">Helper text</label>
                    <Input value={q.helper_text} onChange={e => onChange({ ...q, helper_text: e.target.value })}
                      placeholder="Hint shown below field" className="h-9 text-sm" />
                  </div>
                  <div>
                    <label className="label-xs flex items-center gap-1"><Info size={10} /> Tooltip</label>
                    <Input value={q.tooltip_text || ""} onChange={e => onChange({ ...q, tooltip_text: e.target.value })}
                      placeholder="Info shown on hover (ⓘ icon)" className="h-9 text-sm" />
                  </div>
                </div>

                {/* Step group */}
                <div className="flex items-center gap-3">
                  <div className="w-28">
                    <label className="label-xs">Step group</label>
                    <Input type="number" value={q.step_group ?? 0}
                      onChange={e => onChange({ ...q, step_group: parseInt(e.target.value) || 0 })}
                      className="h-8 text-xs font-mono" min={0} />
                  </div>
                  <p className="text-[10px] text-slate-400 mt-4">Group questions into wizard steps (0 = ungrouped)</p>
                </div>

                {/* Number */}
                {q.type === "number" && (
                  <>
                    <div>
                      <label className="label-xs">Pricing mode</label>
                      <div className="flex gap-3 mt-1">
                        {(["flat", "tiered"] as const).map(m => (
                          <label key={m} className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer select-none">
                            <input type="radio" name={`pm-${idx}`} value={m}
                              checked={(q.pricing_mode || "flat") === m}
                              onChange={() => onChange({ ...q, pricing_mode: m })} className="accent-[#1e40af]" />
                            {m === "flat" ? "Flat rate (£/unit)" : "Tiered pricing"}
                          </label>
                        ))}
                      </div>
                    </div>
                    {(q.pricing_mode || "flat") === "flat" ? (
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="label-xs">Price per unit (£)</label>
                          <Input type="number" value={q.price_per_unit ?? 0}
                            onChange={e => onChange({ ...q, price_per_unit: parseFloat(e.target.value) || 0 })}
                            className="h-9 text-sm font-mono" />
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          {(["min", "max", "step"] as const).map(f => (
                            <div key={f}>
                              <label className="label-xs capitalize">{f}</label>
                              <Input type="number" value={q[f] ?? 0}
                                onChange={e => onChange({ ...q, [f]: parseFloat(e.target.value) || 0 })}
                                className="h-9 text-sm font-mono" />
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="grid grid-cols-3 gap-2">
                          {(["min", "max", "step"] as const).map(f => (
                            <div key={f}>
                              <label className="label-xs capitalize">{f}</label>
                              <Input type="number" value={q[f] ?? 0}
                                onChange={e => onChange({ ...q, [f]: parseFloat(e.target.value) || 0 })}
                                className="h-9 text-sm font-mono" />
                            </div>
                          ))}
                        </div>
                        <TierEditor tiers={q.tiers || []} onChange={tiers => onChange({ ...q, tiers })} />
                      </>
                    )}
                  </>
                )}

                {/* Boolean */}
                {q.type === "boolean" && (
                  <div className="space-y-3">
                    <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer select-none">
                      <input type="checkbox" checked={q.affects_price || false}
                        onChange={e => onChange({ ...q, affects_price: e.target.checked })}
                        className="w-3.5 h-3.5 rounded accent-[#0f172a]" />
                      Affects price
                    </label>
                    {q.affects_price && (
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="label-xs">Price if Yes (£)</label>
                          <Input type="number" value={q.price_for_yes ?? 0}
                            onChange={e => onChange({ ...q, price_for_yes: parseFloat(e.target.value) || 0 })}
                            className="h-9 text-sm font-mono" />
                        </div>
                        <div>
                          <label className="label-xs">Price if No (£)</label>
                          <Input type="number" value={q.price_for_no ?? 0}
                            onChange={e => onChange({ ...q, price_for_no: parseFloat(e.target.value) || 0 })}
                            className="h-9 text-sm font-mono" />
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Dropdown / Multiselect */}
                {hasOptions(q.type) && (
                  <>
                    {q.affects_price && (
                      <div>
                        <label className="label-xs">Price mode</label>
                        <div className="flex gap-3 mt-1">
                          {(["add", "multiply"] as const).map(m => (
                            <label key={m} className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer select-none">
                              <input type="radio" name={`pmode-${idx}`} value={m}
                                checked={q.price_mode === m} onChange={() => onChange({ ...q, price_mode: m })}
                                className="accent-[#1e40af]" />
                              {m === "add" ? "Add / subtract (±£)" : "Multiply (×)"}
                            </label>
                          ))}
                        </div>
                      </div>
                    )}
                    <OptionsEditor options={q.options || []}
                      onChange={opts => onChange({ ...q, options: opts })} affects_price={q.affects_price} />
                  </>
                )}

                {/* Formula */}
                {q.type === "formula" && (
                  <div>
                    <label className="label-xs flex items-center gap-1"><Zap size={10} /> Formula expression</label>
                    <Input value={q.formula_expression || ""}
                      onChange={e => onChange({ ...q, formula_expression: e.target.value })}
                      placeholder="employees * monthly_rate * 0.8" className="h-9 text-sm font-mono" />
                    <p className="text-[10px] text-slate-400 mt-1">
                      Reference other question keys directly. Supports: <code>+  -  *  /  ( )</code> and numeric constants.
                    </p>
                  </div>
                )}

                {/* Date */}
                {q.type === "date" && (
                  <div>
                    <label className="label-xs">Date format</label>
                    <Select value={q.date_format || "date"} onValueChange={v => onChange({ ...q, date_format: v as any })}>
                      <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="date">Single date</SelectItem>
                        <SelectItem value="date_range">Date range (from/to)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {/* File */}
                {q.type === "file" && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="label-xs">Accepted types</label>
                      <Input value={q.accept || ""} onChange={e => onChange({ ...q, accept: e.target.value })}
                        placeholder=".pdf,.docx,.jpg" className="h-9 text-sm font-mono" />
                    </div>
                    <div>
                      <label className="label-xs">Max size (MB)</label>
                      <Input type="number" value={q.max_size_mb ?? 10}
                        onChange={e => onChange({ ...q, max_size_mb: parseFloat(e.target.value) || 10 })}
                        className="h-9 text-sm font-mono" />
                    </div>
                  </div>
                )}

                {/* Flags */}
                <div className="flex flex-wrap gap-4">
                  {(["required", "enabled"] as const).map(flag => (
                    <label key={flag} className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer select-none">
                      <input type="checkbox" checked={q[flag] as boolean}
                        onChange={e => onChange({ ...q, [flag]: e.target.checked })}
                        className="w-3.5 h-3.5 rounded accent-[#0f172a]" />
                      <span className="capitalize">{flag}</span>
                    </label>
                  ))}
                  {hasOptions(q.type) && (
                    <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer select-none">
                      <input type="checkbox" checked={q.affects_price || false}
                        onChange={e => onChange({ ...q, affects_price: e.target.checked })}
                        className="w-3.5 h-3.5 rounded accent-[#0f172a]" />
                      Affects price
                    </label>
                  )}
                </div>

                {/* Visibility rule */}
                <div className="border-t border-slate-100 pt-3">
                <VisibilityRuleEditor rule={q.visibility_rule as any} onChange={r => onChange({ ...q, visibility_rule: r })} otherQuestions={otherQ} />
                </div>
              </>
            )}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

// ── Builder ────────────────────────────────────────────────────────────────────
export function IntakeSchemaBuilder({ schema, onChange }: { schema: IntakeSchemaJson; onChange: (s: IntakeSchemaJson) => void }) {
  const [addOpen, setAddOpen] = useState(false);
  const [showCaps, setShowCaps] = useState(false);
  const questions = schema.questions || [];
  const allKeys = questions.map(q => q.key);

  const update = (qs: IntakeQuestion[]) =>
    onChange({ ...schema, questions: qs.map((q, i) => ({ ...q, order: i })) });

  const addQuestion = (type: QType) => { update([...questions, emptyQuestion(type, questions.length)]); setAddOpen(false); };
  const changeQ = (i: number, q: IntakeQuestion) => { const n = [...questions]; n[i] = q; update(n); };
  const removeQ = (i: number) => update(questions.filter((_, j) => j !== i));
  const moveQ = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= questions.length) return;
    const n = [...questions]; [n[i], n[j]] = [n[j], n[i]]; update(n);
  };

  const typeGroups = ["Choice", "Input", "Pricing", "Layout"];

  return (
    <div className="space-y-3" data-testid="intake-builder">
      {/* Price caps */}
      <div className="rounded-lg border border-slate-200 bg-white">
        <button type="button" onClick={() => setShowCaps(v => !v)}
          className="w-full flex items-center justify-between px-3 py-2.5 text-left hover:bg-slate-50 rounded-lg transition-colors">
          <div className="flex items-center gap-2">
            <Layers size={13} className="text-slate-400" />
            <span className="text-xs font-semibold text-slate-600">Price floor &amp; ceiling caps</span>
          </div>
          <div className="flex items-center gap-2">
            {(schema.price_floor || schema.price_ceiling) && (
              <span title="Caps configured"><AlertCircle size={12} className="text-[#1e40af]" /></span>
            )}
            <ChevronRight size={12} className={`text-slate-400 transition-transform ${showCaps ? "rotate-90" : ""}`} />
          </div>
        </button>
        {showCaps && (
          <div className="px-3 pb-3 border-t border-slate-100 grid grid-cols-2 gap-3 pt-3">
            <div>
              <label className="label-xs">Minimum price (£)</label>
              <Input type="number" value={schema.price_floor ?? ""}
                onChange={e => onChange({ ...schema, price_floor: e.target.value === "" ? null : parseFloat(e.target.value) })}
                placeholder="No minimum" className="h-8 text-xs font-mono" />
            </div>
            <div>
              <label className="label-xs">Maximum price (£)</label>
              <Input type="number" value={schema.price_ceiling ?? ""}
                onChange={e => onChange({ ...schema, price_ceiling: e.target.value === "" ? null : parseFloat(e.target.value) })}
                placeholder="No maximum" className="h-8 text-xs font-mono" />
            </div>
            <p className="col-span-2 text-[10px] text-slate-400">Applied after all calculations.</p>
          </div>
        )}
      </div>

      {/* Empty state */}
      {questions.length === 0 && (
        <div className="border border-dashed border-slate-200 rounded-lg p-8 flex flex-col items-center justify-center text-center bg-slate-50">
          <div className="w-10 h-10 rounded-full bg-white border border-slate-200 flex items-center justify-center mb-3 shadow-sm">
            <List size={18} className="text-slate-400" />
          </div>
          <p className="text-sm font-medium text-slate-500">No intake questions yet</p>
          <p className="text-xs text-slate-400 mt-1">Add questions, content blocks, or formula fields</p>
        </div>
      )}

      {/* Question list */}
      <div className="space-y-2">
        {questions.map((q, i) => (
          <QuestionCard key={i} q={q} idx={i} total={questions.length} allKeys={allKeys}
            allQuestions={questions} onChange={nq => changeQ(i, nq)}
            onRemove={() => removeQ(i)} onMove={dir => moveQ(i, dir)} />
        ))}
      </div>

      {/* Add question popover */}
      <Popover open={addOpen} onOpenChange={setAddOpen}>
        <PopoverTrigger asChild>
          <Button type="button" variant="outline" size="sm" data-testid="intake-add-question"
            className="w-full h-9 border-dashed border-slate-200 text-slate-500 hover:text-slate-700 hover:bg-slate-50 hover:border-slate-300 bg-transparent transition-all">
            <Plus size={14} className="mr-2" /> Add question or content block
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-72 p-2" align="start">
          {typeGroups.map(group => {
            const items = QUESTION_TYPES.filter(t => t.group === group);
            return (
              <div key={group}>
                <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-2 pt-2 pb-1">{group}</p>
                {items.map(qt => (
                  <button key={qt.type} type="button" onClick={() => addQuestion(qt.type)}
                    className="w-full flex items-start gap-3 p-2 rounded-md hover:bg-slate-50 transition-colors text-left"
                    data-testid={`add-q-${qt.type}`}>
                    <span className="text-slate-500 mt-0.5 shrink-0">{qt.icon}</span>
                    <div>
                      <p className="text-sm font-medium text-slate-900">{qt.label}</p>
                      <p className="text-[10px] text-slate-500">{qt.desc}</p>
                    </div>
                  </button>
                ))}
              </div>
            );
          })}
        </PopoverContent>
      </Popover>
    </div>
  );
}
