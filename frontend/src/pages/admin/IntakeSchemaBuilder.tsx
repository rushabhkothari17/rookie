import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  X, Plus, ChevronUp, ChevronDown, ChevronRight,
  Hash, AlignLeft, AlignJustify, List, CheckSquare, GripVertical, ToggleLeft,
  Layers, Eye, AlertCircle,
} from "lucide-react";
import {
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// ── Types ──────────────────────────────────────────────────────────────────────

export type QType = "dropdown" | "multiselect" | "single_line" | "multi_line" | "number" | "boolean";

export interface IntakeOption {
  label: string;
  value: string;
  price_value: number;
}

export interface PricingTier {
  from: number;
  to: number | null;
  price_per_unit: number;
}

export interface VisibilityRule {
  depends_on: string;
  operator: "equals" | "not_equals" | "greater_than" | "less_than" | "contains" | "not_empty";
  value: string;
}

export interface IntakeQuestion {
  key: string;
  label: string;
  helper_text: string;
  required: boolean;
  enabled: boolean;
  order: number;
  type: QType;
  // Dropdown / Multiselect
  affects_price?: boolean;
  price_mode?: "add" | "multiply";
  options?: IntakeOption[];
  // Number type — flat
  price_per_unit?: number;
  pricing_mode?: "flat" | "tiered";
  tiers?: PricingTier[];
  // Number type — bounds
  min?: number;
  max?: number;
  step?: number;
  default_value?: number;
  // Boolean type
  affects_price_boolean?: boolean;
  price_for_yes?: number;
  price_for_no?: number;
  // Conditional visibility
  visibility_rule?: VisibilityRule | null;
}

export interface IntakeSchemaJson {
  version: number;
  updated_at?: string;
  updated_by?: string;
  questions: IntakeQuestion[];
  price_floor?: number | null;
  price_ceiling?: number | null;
}

export const EMPTY_INTAKE_SCHEMA: IntakeSchemaJson = {
  version: 2,
  questions: [],
};

// ── Helpers ────────────────────────────────────────────────────────────────────

const labelToKey = (label: string) =>
  label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40);

const QUESTION_TYPES: { type: QType; label: string; icon: React.ReactNode; desc: string }[] = [
  { type: "dropdown",    label: "Dropdown",     icon: <List size={14} />,         desc: "Single select from options" },
  { type: "multiselect", label: "Multi-select",  icon: <CheckSquare size={14} />,  desc: "Multiple options selectable" },
  { type: "number",      label: "Number",        icon: <Hash size={14} />,         desc: "Numeric with flat or tiered pricing" },
  { type: "boolean",     label: "Yes / No",      icon: <ToggleLeft size={14} />,   desc: "Simple yes or no question" },
  { type: "single_line", label: "Short text",    icon: <AlignLeft size={14} />,    desc: "One-line text answer" },
  { type: "multi_line",  label: "Long text",     icon: <AlignJustify size={14} />, desc: "Paragraph text answer" },
];

const TYPE_LABELS: Record<QType, string> = {
  dropdown: "Dropdown", multiselect: "Multi-select",
  number: "Number", boolean: "Yes / No",
  single_line: "Short text", multi_line: "Long text",
};

const emptyQuestion = (type: QType, order: number): IntakeQuestion => ({
  key: "", label: "", helper_text: "", required: false, enabled: true,
  order, type,
  ...(type === "dropdown" || type === "multiselect"
    ? { affects_price: false, price_mode: "add", options: [] }
    : {}),
  ...(type === "number"
    ? { price_per_unit: 0, pricing_mode: "flat", tiers: [], min: 0, max: 1000, step: 1, default_value: 0 }
    : {}),
  ...(type === "boolean"
    ? { affects_price_boolean: false, price_for_yes: 0, price_for_no: 0 }
    : {}),
});

const hasOptions = (t: QType) => t === "dropdown" || t === "multiselect";

// ── Option Editor ──────────────────────────────────────────────────────────────

function OptionsEditor({
  options, onChange, affects_price,
}: { options: IntakeOption[]; onChange: (v: IntakeOption[]) => void; affects_price?: boolean }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Options</span>
        {affects_price && <span className="text-[10px] text-slate-400">Price adj. (£)</span>}
      </div>
      {options.length > 0 && (
        <div className="space-y-1.5">
          {options.map((opt, i) => (
            <div key={i} className="flex gap-2 items-center">
              <Input
                value={opt.label}
                onChange={e => {
                  const n = [...options];
                  n[i] = { ...n[i], label: e.target.value, value: labelToKey(e.target.value) };
                  onChange(n);
                }}
                placeholder="Option label"
                className="h-8 text-xs flex-1"
              />
              {affects_price && (
                <Input
                  type="number"
                  value={opt.price_value ?? 0}
                  onChange={e => {
                    const n = [...options];
                    n[i] = { ...n[i], price_value: parseFloat(e.target.value) || 0 };
                    onChange(n);
                  }}
                  placeholder="0"
                  className="h-8 text-xs w-20 font-mono"
                />
              )}
              <button type="button" onClick={() => onChange(options.filter((_, j) => j !== i))}
                className="text-slate-400 hover:text-red-500 transition-colors">
                <X size={13} />
              </button>
            </div>
          ))}
        </div>
      )}
      <Button type="button" variant="outline" size="sm"
        onClick={() => onChange([...options, { label: "", value: "", price_value: 0 }])}
        className="h-7 text-xs px-2 text-slate-500 hover:text-slate-700">
        <Plus size={11} className="mr-1" /> Add option
      </Button>
    </div>
  );
}

// ── Tier Editor ────────────────────────────────────────────────────────────────

function TierEditor({ tiers, onChange }: { tiers: PricingTier[]; onChange: (t: PricingTier[]) => void }) {
  const addTier = () => {
    const lastTo = tiers.length > 0 ? (tiers[tiers.length - 1].to ?? 0) : 0;
    onChange([...tiers, { from: lastTo, to: null, price_per_unit: 0 }]);
  };
  const updateTier = (i: number, field: keyof PricingTier, val: any) => {
    const n = [...tiers];
    n[i] = { ...n[i], [field]: val };
    onChange(n);
  };
  return (
    <div className="space-y-2" data-testid="tier-editor">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Pricing tiers</span>
        <button type="button" onClick={addTier} data-testid="tier-add-btn"
          className="flex items-center gap-1 text-xs text-[#1e40af] hover:text-blue-700 font-medium transition-colors">
          <Plus size={11} /> Add tier
        </button>
      </div>
      {tiers.length === 0 && (
        <p className="text-xs text-slate-400 italic">No tiers yet — click "Add tier" to start</p>
      )}
      {tiers.length > 0 && (
        <div className="space-y-1.5">
          <div className="grid grid-cols-[1fr_1fr_1fr_24px] gap-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider px-0.5">
            <span>From</span><span>To (blank=∞)</span><span>£/unit</span><span></span>
          </div>
          {tiers.map((tier, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_1fr_24px] gap-2 items-center" data-testid="tier-row">
              <Input type="number" value={tier.from ?? 0}
                onChange={e => updateTier(i, "from", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs font-mono" placeholder="0" />
              <Input type="number" value={tier.to ?? ""}
                onChange={e => updateTier(i, "to", e.target.value === "" ? null : parseFloat(e.target.value))}
                className="h-8 text-xs font-mono" placeholder="∞" />
              <Input type="number" value={tier.price_per_unit ?? 0}
                onChange={e => updateTier(i, "price_per_unit", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs font-mono" placeholder="0" />
              <button type="button" onClick={() => onChange(tiers.filter((_, j) => j !== i))}
                className="text-slate-400 hover:text-red-500 transition-colors">
                <X size={12} />
              </button>
            </div>
          ))}
          <p className="text-[10px] text-slate-400 mt-1">Progressive pricing: first N units at rate 1, next N at rate 2, etc.</p>
        </div>
      )}
    </div>
  );
}

// ── Visibility Rule Editor ─────────────────────────────────────────────────────

const OPERATORS = [
  { value: "equals", label: "= equals" },
  { value: "not_equals", label: "≠ not equals" },
  { value: "greater_than", label: "> greater than" },
  { value: "less_than", label: "< less than" },
  { value: "contains", label: "contains" },
  { value: "not_empty", label: "is not empty" },
];

function VisibilityRuleEditor({
  rule, onChange, otherQuestions,
}: {
  rule: VisibilityRule | null | undefined;
  onChange: (r: VisibilityRule | null) => void;
  otherQuestions: IntakeQuestion[];
}) {
  const hasRule = !!rule;
  return (
    <div className="space-y-2" data-testid="visibility-rule-section">
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer select-none">
          <Eye size={11} /> Visibility rule
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={hasRule}
            onChange={e => e.target.checked
              ? onChange({ depends_on: "", operator: "equals", value: "" })
              : onChange(null)
            }
            className="w-3 h-3 rounded accent-[#0f172a]"
            data-testid="vis-rule-toggle"
          />
          {hasRule ? "On" : "Off"}
        </label>
      </div>
      {hasRule && rule && (
        <div className="bg-blue-50/60 border border-blue-100 rounded-lg p-3 space-y-2">
          <p className="text-[11px] text-blue-600 font-medium">Show this question only when:</p>
          <div className="grid grid-cols-[1fr_1fr] gap-2">
            <div>
              <label className="text-[10px] text-slate-500 block mb-1">Question</label>
              <Select
                value={rule.depends_on || ""}
                onValueChange={v => onChange({ ...rule, depends_on: v })}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Select question…" />
                </SelectTrigger>
                <SelectContent>
                  {otherQuestions.map(q => (
                    <SelectItem key={q.key} value={q.key}>
                      {q.label || q.key || "(untitled)"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] text-slate-500 block mb-1">Condition</label>
              <Select
                value={rule.operator}
                onValueChange={v => onChange({ ...rule, operator: v as any })}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {OPERATORS.map(op => (
                    <SelectItem key={op.value} value={op.value}>{op.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {rule.operator !== "not_empty" && (
            <div>
              <label className="text-[10px] text-slate-500 block mb-1">Value</label>
              <Input
                value={rule.value || ""}
                onChange={e => onChange({ ...rule, value: e.target.value })}
                placeholder="e.g. yes, 5, premium"
                className="h-8 text-xs"
              />
            </div>
          )}
        </div>
      )}
      {!hasRule && otherQuestions.length === 0 && (
        <p className="text-[10px] text-slate-400 italic">Add more questions to enable visibility rules</p>
      )}
    </div>
  );
}

// ── Question Card ──────────────────────────────────────────────────────────────

function QuestionCard({
  q, idx, total, allKeys, allQuestions, onChange, onRemove, onMove,
}: {
  q: IntakeQuestion; idx: number; total: number; allKeys: string[];
  allQuestions: IntakeQuestion[];
  onChange: (q: IntakeQuestion) => void; onRemove: () => void; onMove: (dir: -1 | 1) => void;
}) {
  const [open, setOpen] = useState(true);
  const isDuplicate = q.key !== "" && allKeys.filter(k => k === q.key).length > 1;
  const typeInfo = QUESTION_TYPES.find(t => t.type === q.type);
  const otherQuestions = allQuestions.filter((_, i) => i !== idx).filter(oq => oq.key);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="group bg-white border border-slate-200 rounded-lg overflow-hidden transition-all hover:border-slate-300 shadow-sm" data-testid="question-card" data-q-type={q.type}>
        {/* Header */}
        <CollapsibleTrigger asChild>
          <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-slate-50 select-none transition-colors">
            <GripVertical size={14} className="text-slate-300 shrink-0" />
            <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-600 shrink-0">
              {typeInfo?.icon}
              {TYPE_LABELS[q.type]}
            </span>
            <span className="text-sm font-medium text-slate-900 flex-1 truncate">
              {q.label || <span className="text-slate-400 font-normal italic">Untitled question</span>}
            </span>
            {q.visibility_rule && (
              <span className="shrink-0" title="Has visibility rule"><Eye size={12} className="text-blue-400" /></span>
            )}
            {!q.enabled && <span className="text-[10px] text-slate-400 shrink-0">disabled</span>}
            <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
              <button type="button" onClick={e => { e.stopPropagation(); onMove(-1); }} disabled={idx === 0}
                className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-25 rounded">
                <ChevronUp size={13} />
              </button>
              <button type="button" onClick={e => { e.stopPropagation(); onMove(1); }} disabled={idx === total - 1}
                className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-25 rounded">
                <ChevronDown size={13} />
              </button>
              <button type="button" onClick={e => { e.stopPropagation(); onRemove(); }}
                className="p-1 text-slate-400 hover:text-red-500 rounded transition-colors">
                <X size={13} />
              </button>
            </div>
            <ChevronRight size={14} className={`text-slate-400 transition-transform shrink-0 ${open ? "rotate-90" : ""}`} />
          </div>
        </CollapsibleTrigger>

        {/* Body */}
        <CollapsibleContent>
          <div className="px-4 pb-4 pt-3 border-t border-slate-100 bg-slate-50/50 space-y-4">
            {/* Label + Key */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Label *</label>
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
                }`}>
                  {q.key || <span className="italic text-slate-300">auto</span>}
                </div>
              </div>
            </div>

            {/* Helper text */}
            <div>
              <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Helper text</label>
              <Input value={q.helper_text}
                onChange={e => onChange({ ...q, helper_text: e.target.value })}
                placeholder="Hint shown below the question" className="h-9 text-sm" />
            </div>

            {/* Number fields */}
            {q.type === "number" && (
              <>
                <div>
                  <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-2">Pricing mode</label>
                  <div className="flex gap-3">
                    {(["flat", "tiered"] as const).map(m => (
                      <label key={m} className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer select-none">
                        <input type="radio" name={`pm-${idx}`} value={m}
                          checked={(q.pricing_mode || "flat") === m}
                          onChange={() => onChange({ ...q, pricing_mode: m })}
                          className="accent-[#1e40af]"
                          data-testid={`pricing-mode-${m}`} />
                        {m === "flat" ? "Flat rate (£/unit)" : "Tiered pricing"}
                      </label>
                    ))}
                  </div>
                </div>

                {(q.pricing_mode || "flat") === "flat" ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Price per unit (£)</label>
                      <Input type="number" value={q.price_per_unit ?? 0}
                        onChange={e => onChange({ ...q, price_per_unit: parseFloat(e.target.value) || 0 })}
                        placeholder="0" className="h-9 text-sm font-mono" />
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      {(["min", "max", "step"] as const).map(field => (
                        <div key={field}>
                          <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5 capitalize">{field}</label>
                          <Input type="number" value={q[field] ?? 0}
                            onChange={e => onChange({ ...q, [field]: parseFloat(e.target.value) || 0 })}
                            className="h-9 text-sm font-mono" />
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-3 gap-2">
                      {(["min", "max", "step"] as const).map(field => (
                        <div key={field}>
                          <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5 capitalize">{field}</label>
                          <Input type="number" value={q[field] ?? 0}
                            onChange={e => onChange({ ...q, [field]: parseFloat(e.target.value) || 0 })}
                            className="h-9 text-sm font-mono" />
                        </div>
                      ))}
                    </div>
                    <TierEditor tiers={q.tiers || []} onChange={tiers => onChange({ ...q, tiers })} />
                  </>
                )}
              </>
            )}

            {/* Boolean / Yes-No pricing */}
            {q.type === "boolean" && (
              <div className="space-y-3">
                <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer select-none">
                  <input type="checkbox" checked={q.affects_price_boolean || false}
                    onChange={e => onChange({ ...q, affects_price_boolean: e.target.checked })}
                    className="w-3.5 h-3.5 rounded accent-[#0f172a]"
                    data-testid="boolean-affects-price" />
                  Affects price
                </label>
                {q.affects_price_boolean && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Price if Yes (£)</label>
                      <Input type="number" value={q.price_for_yes ?? 0}
                        onChange={e => onChange({ ...q, price_for_yes: parseFloat(e.target.value) || 0 })}
                        className="h-9 text-sm font-mono" />
                    </div>
                    <div>
                      <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Price if No (£)</label>
                      <Input type="number" value={q.price_for_no ?? 0}
                        onChange={e => onChange({ ...q, price_for_no: parseFloat(e.target.value) || 0 })}
                        className="h-9 text-sm font-mono" />
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Options for dropdown / multiselect */}
            {hasOptions(q.type) && (
              <>
                {q.affects_price && (
                  <div>
                    <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-2">Price mode</label>
                    <div className="flex gap-3">
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
                  onChange={opts => onChange({ ...q, options: opts })}
                  affects_price={q.affects_price} />
              </>
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
              <VisibilityRuleEditor
                rule={q.visibility_rule}
                onChange={r => onChange({ ...q, visibility_rule: r })}
                otherQuestions={otherQuestions}
              />
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

// ── Builder ────────────────────────────────────────────────────────────────────

export function IntakeSchemaBuilder({
  schema, onChange,
}: { schema: IntakeSchemaJson; onChange: (s: IntakeSchemaJson) => void }) {
  const [addOpen, setAddOpen] = useState(false);
  const [showCaps, setShowCaps] = useState(false);
  const questions = schema.questions || [];
  const allKeys = questions.map(q => q.key);

  const update = (qs: IntakeQuestion[]) =>
    onChange({ ...schema, questions: qs.map((q, i) => ({ ...q, order: i })) });

  const addQuestion = (type: QType) => {
    update([...questions, emptyQuestion(type, questions.length)]);
    setAddOpen(false);
  };

  const changeQ = (i: number, q: IntakeQuestion) => {
    const n = [...questions]; n[i] = q; update(n);
  };

  const removeQ = (i: number) => update(questions.filter((_, j) => j !== i));

  const moveQ = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= questions.length) return;
    const n = [...questions];
    [n[i], n[j]] = [n[j], n[i]];
    update(n);
  };

  return (
    <div className="space-y-3" data-testid="intake-builder">
      {/* Price floor/ceiling caps */}
      <div className="rounded-lg border border-slate-200 bg-white">
        <button
          type="button"
          onClick={() => setShowCaps(v => !v)}
          data-testid="price-caps-toggle"
          className="w-full flex items-center justify-between px-3 py-2.5 text-left hover:bg-slate-50 rounded-lg transition-colors"
        >
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
              <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Minimum price (£)</label>
              <Input type="number" value={schema.price_floor ?? ""}
                onChange={e => onChange({ ...schema, price_floor: e.target.value === "" ? null : parseFloat(e.target.value) })}
                placeholder="No minimum" className="h-8 text-xs font-mono" />
            </div>
            <div>
              <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Maximum price (£)</label>
              <Input type="number" value={schema.price_ceiling ?? ""}
                onChange={e => onChange({ ...schema, price_ceiling: e.target.value === "" ? null : parseFloat(e.target.value) })}
                placeholder="No maximum" className="h-8 text-xs font-mono" />
            </div>
            <p className="col-span-2 text-[10px] text-slate-400">Applied after all question calculations. Useful to enforce minimum billing or cap variable pricing.</p>
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
          <p className="text-xs text-slate-400 mt-1">Add questions customers answer before checkout</p>
        </div>
      )}

      {/* Question list */}
      <div className="space-y-2">
        {questions.map((q, i) => (
          <QuestionCard
            key={i} q={q} idx={i} total={questions.length} allKeys={allKeys}
            allQuestions={questions}
            onChange={nq => changeQ(i, nq)}
            onRemove={() => removeQ(i)}
            onMove={dir => moveQ(i, dir)}
          />
        ))}
      </div>

      {/* Add question */}
      <Popover open={addOpen} onOpenChange={setAddOpen}>
        <PopoverTrigger asChild>
          <Button type="button" variant="outline" size="sm" data-testid="intake-add-question"
            className="w-full h-9 border-dashed border-slate-200 text-slate-500 hover:text-slate-700 hover:bg-slate-50 hover:border-slate-300 bg-transparent transition-all">
            <Plus size={14} className="mr-2" /> Add question
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-64 p-2" align="start">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-2 py-1.5">Question type</p>
          {QUESTION_TYPES.map(qt => (
            <button key={qt.type} type="button" onClick={() => addQuestion(qt.type)}
              className="w-full flex items-start gap-3 p-2.5 rounded-md hover:bg-slate-50 transition-colors text-left"
              data-testid={`add-q-${qt.type}`}>
              <span className="text-slate-500 mt-0.5 shrink-0">{qt.icon}</span>
              <div>
                <p className="text-sm font-medium text-slate-900">{qt.label}</p>
                <p className="text-[11px] text-slate-500">{qt.desc}</p>
              </div>
            </button>
          ))}
        </PopoverContent>
      </Popover>
    </div>
  );
}
