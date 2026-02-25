import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  X, Plus, ChevronUp, ChevronDown, ChevronRight,
  Hash, AlignLeft, AlignJustify, List, CheckSquare, GripVertical,
} from "lucide-react";
import {
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

// ── Types ──────────────────────────────────────────────────────────────────────

export type QType = "dropdown" | "multiselect" | "single_line" | "multi_line" | "number";

export interface IntakeOption {
  label: string;
  value: string;
  price_value: number;
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
  // Number type
  price_per_unit?: number;
  min?: number;
  max?: number;
  step?: number;
  default_value?: number;
}

export interface IntakeSchemaJson {
  version: number;
  updated_at?: string;
  updated_by?: string;
  questions: IntakeQuestion[];
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
  { type: "number",      label: "Number",        icon: <Hash size={14} />,         desc: "Numeric input with optional per-unit pricing" },
  { type: "single_line", label: "Short text",    icon: <AlignLeft size={14} />,    desc: "One-line text answer" },
  { type: "multi_line",  label: "Long text",     icon: <AlignJustify size={14} />, desc: "Paragraph text answer" },
];

const TYPE_LABELS: Record<QType, string> = {
  dropdown: "Dropdown", multiselect: "Multi-select",
  number: "Number", single_line: "Short text", multi_line: "Long text",
};

const emptyQuestion = (type: QType, order: number): IntakeQuestion => ({
  key: "", label: "", helper_text: "", required: false, enabled: true,
  order, type,
  ...(type === "dropdown" || type === "multiselect"
    ? { affects_price: false, price_mode: "add", options: [] }
    : {}),
  ...(type === "number"
    ? { price_per_unit: 0, min: 0, max: 1000, step: 1, default_value: 0 }
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
        <span className="text-[11px] font-semibold text-[#94a3b8] uppercase tracking-wider">Options</span>
        {affects_price && (
          <span className="text-[10px] text-[#94a3b8]">Price adj.</span>
        )}
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
                className="h-8 text-xs bg-[#0f172a] border-[#334155] text-[#f8fafc] placeholder:text-[#64748b] focus:ring-1 focus:ring-[#dc2626] focus:border-[#dc2626] flex-1"
                data-testid={`opt-label-${i}`}
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
                  className="h-8 text-xs w-20 font-mono bg-[#0f172a] border-[#334155] text-[#f8fafc] focus:ring-1 focus:ring-[#dc2626] focus:border-[#dc2626]"
                  data-testid={`opt-price-${i}`}
                />
              )}
              <button
                type="button"
                onClick={() => onChange(options.filter((_, j) => j !== i))}
                className="text-[#475569] hover:text-red-400 transition-colors"
              >
                <X size={13} />
              </button>
            </div>
          ))}
        </div>
      )}
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onChange([...options, { label: "", value: "", price_value: 0 }])}
        className="h-7 text-xs px-2 bg-transparent border-[#334155] text-[#94a3b8] hover:bg-[#1e293b] hover:text-[#f8fafc]"
      >
        <Plus size={11} className="mr-1" /> Add option
      </Button>
    </div>
  );
}

// ── Question Card ──────────────────────────────────────────────────────────────

function QuestionCard({
  q, idx, total, allKeys, onChange, onRemove, onMove,
}: {
  q: IntakeQuestion; idx: number; total: number; allKeys: string[];
  onChange: (q: IntakeQuestion) => void; onRemove: () => void; onMove: (dir: -1 | 1) => void;
}) {
  const [open, setOpen] = useState(true);
  const isDuplicate = q.key !== "" && allKeys.filter(k => k === q.key).length > 1;
  const typeInfo = QUESTION_TYPES.find(t => t.type === q.type);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="group bg-[#1e293b] border border-[#334155] rounded-lg overflow-hidden transition-all hover:border-[#475569]">
        {/* Header */}
        <CollapsibleTrigger asChild>
          <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-[#334155]/20 select-none">
            <GripVertical size={14} className="text-[#475569] shrink-0" />
            <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-[#0f172a] border border-[#334155] text-[#94a3b8] shrink-0">
              {typeInfo?.icon}
              {TYPE_LABELS[q.type]}
            </span>
            <span className="text-sm font-medium text-[#f8fafc] flex-1 truncate">
              {q.label || <span className="text-[#475569] font-normal italic">Untitled question</span>}
            </span>
            {!q.enabled && (
              <span className="text-[10px] text-[#475569] shrink-0">disabled</span>
            )}
            <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
              <button type="button" onClick={e => { e.stopPropagation(); onMove(-1); }} disabled={idx === 0}
                className="p-1 text-[#64748b] hover:text-[#f8fafc] disabled:opacity-25 rounded">
                <ChevronUp size={13} />
              </button>
              <button type="button" onClick={e => { e.stopPropagation(); onMove(1); }} disabled={idx === total - 1}
                className="p-1 text-[#64748b] hover:text-[#f8fafc] disabled:opacity-25 rounded">
                <ChevronDown size={13} />
              </button>
              <button type="button" onClick={e => { e.stopPropagation(); onRemove(); }}
                className="p-1 text-[#475569] hover:text-red-400 rounded transition-colors">
                <X size={13} />
              </button>
            </div>
            <ChevronRight size={14} className={`text-[#475569] transition-transform shrink-0 ${open ? "rotate-90" : ""}`} />
          </div>
        </CollapsibleTrigger>

        {/* Body */}
        <CollapsibleContent>
          <div className="px-4 pb-4 pt-3 border-t border-[#334155] bg-[#0f172a]/40 space-y-4">
            {/* Label + Key */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-medium text-[#94a3b8] block mb-1.5">Label *</label>
                <Input
                  value={q.label}
                  onChange={e => onChange({ ...q, label: e.target.value, key: labelToKey(e.target.value) })}
                  placeholder="Question label"
                  className="h-9 text-sm bg-[#0f172a] border-[#334155] text-[#f8fafc] placeholder:text-[#475569] focus:ring-1 focus:ring-[#dc2626] focus:border-[#dc2626]"
                />
              </div>
              <div>
                <label className={`text-[11px] font-medium block mb-1.5 ${isDuplicate ? "text-red-400" : "text-[#64748b]"}`}>
                  Key {isDuplicate && <span className="text-red-400">(duplicate!)</span>}
                </label>
                <div className={`h-9 flex items-center px-3 rounded-md border text-xs font-mono ${
                  isDuplicate ? "border-red-500/50 text-red-400 bg-red-950/20" : "border-[#334155] text-[#475569] bg-[#0f172a]/60"
                }`}>
                  {q.key || <span className="italic text-[#334155]">auto</span>}
                </div>
              </div>
            </div>

            {/* Helper text */}
            <div>
              <label className="text-[11px] font-medium text-[#94a3b8] block mb-1.5">Helper text</label>
              <Input
                value={q.helper_text}
                onChange={e => onChange({ ...q, helper_text: e.target.value })}
                placeholder="Hint shown below the question"
                className="h-9 text-sm bg-[#0f172a] border-[#334155] text-[#f8fafc] placeholder:text-[#475569] focus:ring-1 focus:ring-[#dc2626] focus:border-[#dc2626]"
              />
            </div>

            {/* Number fields */}
            {q.type === "number" && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-medium text-[#94a3b8] block mb-1.5">Price per unit (£)</label>
                  <Input
                    type="number"
                    value={q.price_per_unit ?? 0}
                    onChange={e => onChange({ ...q, price_per_unit: parseFloat(e.target.value) || 0 })}
                    placeholder="0"
                    className="h-9 text-sm font-mono bg-[#0f172a] border-[#334155] text-[#f8fafc] focus:ring-1 focus:ring-[#dc2626] focus:border-[#dc2626]"
                    data-testid={`pf-q-price-per-unit-${idx}`}
                  />
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {(["min", "max", "step"] as const).map(field => (
                    <div key={field}>
                      <label className="text-[11px] font-medium text-[#94a3b8] block mb-1.5 capitalize">{field}</label>
                      <Input
                        type="number"
                        value={q[field] ?? 0}
                        onChange={e => onChange({ ...q, [field]: parseFloat(e.target.value) || 0 })}
                        className="h-9 text-sm font-mono bg-[#0f172a] border-[#334155] text-[#f8fafc] focus:ring-1 focus:ring-[#dc2626] focus:border-[#dc2626]"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Options for dropdown / multiselect */}
            {hasOptions(q.type) && (
              <>
                {q.affects_price && (
                  <div>
                    <label className="text-[11px] font-medium text-[#94a3b8] block mb-2">Price mode</label>
                    <div className="flex gap-3">
                      {(["add", "multiply"] as const).map(m => (
                        <label key={m} className="flex items-center gap-2 text-xs text-[#94a3b8] cursor-pointer select-none">
                          <input
                            type="radio"
                            name={`pm-${idx}-${q.key}`}
                            value={m}
                            checked={q.price_mode === m}
                            onChange={() => onChange({ ...q, price_mode: m })}
                            className="accent-[#dc2626]"
                          />
                          {m === "add" ? "Add / subtract (±£)" : "Multiply (×)"}
                        </label>
                      ))}
                    </div>
                  </div>
                )}
                <OptionsEditor
                  options={q.options || []}
                  onChange={opts => onChange({ ...q, options: opts })}
                  affects_price={q.affects_price}
                />
              </>
            )}

            {/* Flags */}
            <div className="flex flex-wrap gap-4">
              {(["required", "enabled"] as const).map(flag => (
                <label key={flag} className="flex items-center gap-2 text-xs text-[#94a3b8] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={q[flag] as boolean}
                    onChange={e => onChange({ ...q, [flag]: e.target.checked })}
                    className="w-3.5 h-3.5 rounded accent-[#dc2626]"
                  />
                  <span className="capitalize">{flag}</span>
                </label>
              ))}
              {hasOptions(q.type) && (
                <label className="flex items-center gap-2 text-xs text-[#94a3b8] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={q.affects_price || false}
                    onChange={e => onChange({ ...q, affects_price: e.target.checked })}
                    className="w-3.5 h-3.5 rounded accent-[#dc2626]"
                  />
                  Affects price
                </label>
              )}
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
      {/* Empty state */}
      {questions.length === 0 && (
        <div className="border border-dashed border-[#334155] rounded-lg p-8 flex flex-col items-center justify-center text-center bg-[#1e293b]/20">
          <div className="w-10 h-10 rounded-full bg-[#1e293b] border border-[#334155] flex items-center justify-center mb-3">
            <List size={18} className="text-[#475569]" />
          </div>
          <p className="text-sm font-medium text-[#64748b]">No intake questions yet</p>
          <p className="text-xs text-[#475569] mt-1">Add questions customers answer before checkout</p>
        </div>
      )}

      {/* Question list */}
      <div className="space-y-2">
        {questions.map((q, i) => (
          <QuestionCard
            key={i}
            q={q}
            idx={i}
            total={questions.length}
            allKeys={allKeys}
            onChange={nq => changeQ(i, nq)}
            onRemove={() => removeQ(i)}
            onMove={dir => moveQ(i, dir)}
          />
        ))}
      </div>

      {/* Add question */}
      <Popover open={addOpen} onOpenChange={setAddOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            data-testid="intake-add-question"
            className="w-full h-9 border-dashed border-[#334155] text-[#94a3b8] hover:text-[#f8fafc] hover:bg-[#1e293b] hover:border-[#475569] bg-transparent transition-all"
          >
            <Plus size={14} className="mr-2" /> Add question
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className="w-64 p-2 bg-[#1e293b] border-[#334155] shadow-2xl"
          align="start"
        >
          <p className="text-[11px] font-semibold text-[#64748b] uppercase tracking-wider px-2 py-1.5">Question type</p>
          {QUESTION_TYPES.map(qt => (
            <button
              key={qt.type}
              type="button"
              onClick={() => addQuestion(qt.type)}
              className="w-full flex items-start gap-3 p-2.5 rounded-md hover:bg-[#334155] transition-colors text-left"
              data-testid={`add-q-${qt.type}`}
            >
              <span className="text-[#94a3b8] mt-0.5 shrink-0">{qt.icon}</span>
              <div>
                <p className="text-sm font-medium text-[#f8fafc]">{qt.label}</p>
                <p className="text-[11px] text-[#64748b]">{qt.desc}</p>
              </div>
            </button>
          ))}
        </PopoverContent>
      </Popover>
    </div>
  );
}
