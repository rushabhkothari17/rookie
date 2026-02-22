import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { X, Plus, ChevronUp, ChevronDown } from "lucide-react";

export interface IntakeOption { label: string; value: string; price_value: number; }

export interface IntakeQuestion {
  key: string;
  label: string;
  helper_text: string;
  required: boolean;
  enabled: boolean;
  order: number;
  affects_price: boolean;
  price_mode: "add" | "multiply";
  options: IntakeOption[];
}

export interface IntakeQuestions {
  dropdown: IntakeQuestion[];
  multiselect: IntakeQuestion[];
  single_line: IntakeQuestion[];
  multi_line: IntakeQuestion[];
}

export interface IntakeSchemaJson {
  version: number;
  updated_at?: string;
  updated_by?: string;
  questions: IntakeQuestions;
}

export const EMPTY_INTAKE_SCHEMA: IntakeSchemaJson = {
  version: 1,
  questions: { dropdown: [], multiselect: [], single_line: [], multi_line: [] },
};

const MAX = 10;
type QType = keyof IntakeQuestions;
const TABS: { key: QType; label: string; hasOptions: boolean }[] = [
  { key: "dropdown", label: "Dropdown", hasOptions: true },
  { key: "multiselect", label: "Multi-select", hasOptions: true },
  { key: "single_line", label: "Single-line", hasOptions: false },
  { key: "multi_line", label: "Multi-line", hasOptions: false },
];

const labelToKey = (label: string) =>
  label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40);

const emptyQ = (order: number): IntakeQuestion => ({
  key: "", label: "", helper_text: "", required: false, enabled: true,
  order, affects_price: false, price_mode: "add", options: [],
});

function OptionsEditor({ options, onChange, affects_price }: {
  options: IntakeOption[];
  onChange: (v: IntakeOption[]) => void;
  affects_price?: boolean;
}) {
  const updateLabel = (i: number, label: string) => {
    const n = [...options];
    const autoValue = labelToKey(label);
    n[i] = { ...n[i], label, value: autoValue };
    onChange(n);
  };
  const updatePrice = (i: number, price_value: number) => {
    const n = [...options]; n[i] = { ...n[i], price_value }; onChange(n);
  };
  const move = (i: number, dir: -1 | 1) => {
    const n = [...options]; const j = i + dir;
    if (j < 0 || j >= n.length) return;
    [n[i], n[j]] = [n[j], n[i]]; onChange(n);
  };
  return (
    <div className="ml-3 border-l-2 border-slate-200 pl-3 mt-2 space-y-1.5">
      <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">Options</p>
      {options.length > 0 && (
        <div className="flex gap-1 items-center text-[10px] text-slate-400 font-medium px-0.5">
          <span className="flex-1">Display label</span>
          {affects_price && <span className="w-20 text-blue-400">Price adj ($)</span>}
          <span className="w-16" />
        </div>
      )}
      {options.map((opt, i) => (
        <div key={i} className="flex gap-1 items-center">
          <Input value={opt.label} onChange={e => updateLabel(i, e.target.value)} placeholder="Option label" className="h-7 text-xs flex-1" data-testid={`opt-label-${i}`} />
          {affects_price && (
            <Input
              type="number"
              value={opt.price_value ?? 0}
              onChange={e => updatePrice(i, parseFloat(e.target.value) || 0)}
              placeholder="0"
              className="h-7 text-xs w-20 font-mono"
              data-testid={`opt-price-${i}`}
            />
          )}
          <button type="button" onClick={() => move(i, -1)} disabled={i === 0} className="text-slate-400 hover:text-slate-600 disabled:opacity-25 shrink-0"><ChevronUp size={12} /></button>
          <button type="button" onClick={() => move(i, 1)} disabled={i === options.length - 1} className="text-slate-400 hover:text-slate-600 disabled:opacity-25 shrink-0"><ChevronDown size={12} /></button>
          <button type="button" onClick={() => onChange(options.filter((_, j) => j !== i))} className="text-red-400 hover:text-red-600 shrink-0"><X size={12} /></button>
        </div>
      ))}
      <Button type="button" variant="outline" size="sm" onClick={() => onChange([...options, { label: "", value: "", price_value: 0 }])} className="h-6 text-xs px-2">
        <Plus size={11} className="mr-1" /> Option
      </Button>
    </div>
  );
}

function QuestionEditor({ q, idx, total, allKeys, hasOptions, onChange, onRemove, onMove }: {
  q: IntakeQuestion; idx: number; total: number; allKeys: string[];
  hasOptions: boolean; onChange: (q: IntakeQuestion) => void; onRemove: () => void; onMove: (dir: -1 | 1) => void;
}) {
  const isDuplicate = q.key !== "" && allKeys.filter(k => k === q.key).length > 1;

  const handleLabelChange = (v: string) => {
    onChange({ ...q, label: v, key: labelToKey(v) });
  };

  return (
    <div className="border border-slate-200 rounded-lg p-3 space-y-2.5 bg-white">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-slate-400">Q{idx + 1}</span>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => onMove(-1)} disabled={idx === 0} className="p-0.5 text-slate-400 hover:text-slate-700 disabled:opacity-25"><ChevronUp size={13} /></button>
          <button type="button" onClick={() => onMove(1)} disabled={idx === total - 1} className="p-0.5 text-slate-400 hover:text-slate-700 disabled:opacity-25"><ChevronDown size={13} /></button>
          <button type="button" onClick={onRemove} className="p-0.5 text-red-400 hover:text-red-600"><X size={13} /></button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[11px] text-slate-500">Label *</label>
          <Input value={q.label} onChange={e => handleLabelChange(e.target.value)} placeholder="Question label" className="h-7 text-xs mt-0.5" />
        </div>
        <div>
          <label className={`text-[11px] ${isDuplicate ? "text-red-500 font-semibold" : "text-slate-400"}`}>
            Key (auto) {isDuplicate && <span className="text-red-500">(duplicate!)</span>}
          </label>
          <div
            className={`mt-0.5 h-7 flex items-center px-2 rounded border bg-slate-50 text-xs font-mono overflow-hidden ${
              isDuplicate ? "border-red-300 text-red-500" : "border-slate-200 text-slate-400"
            }`}
            title="Auto-generated from label"
          >
            {q.key || <span className="text-slate-300 italic">auto</span>}
          </div>
        </div>
      </div>

      <div>
        <label className="text-[11px] text-slate-500">Helper text (optional)</label>
        <Input value={q.helper_text} onChange={e => onChange({ ...q, helper_text: e.target.value })} placeholder="Hint shown below the question" className="h-7 text-xs mt-0.5" />
      </div>

      <div className="flex flex-wrap gap-4 text-xs">
        <label className="flex items-center gap-1.5 cursor-pointer select-none">
          <input type="checkbox" checked={q.required} onChange={e => onChange({ ...q, required: e.target.checked })} className="w-3.5 h-3.5" />
          Required
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer select-none">
          <input type="checkbox" checked={q.enabled} onChange={e => onChange({ ...q, enabled: e.target.checked })} className="w-3.5 h-3.5" />
          Enabled
        </label>
        {hasOptions && (
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input type="checkbox" checked={q.affects_price} onChange={e => onChange({ ...q, affects_price: e.target.checked })} className="w-3.5 h-3.5" />
            Affects price
          </label>
        )}
      </div>

      {hasOptions && q.affects_price && (
        <div>
          <label className="text-[11px] text-slate-500">Price adjustment mode</label>
          <div className="flex gap-2 mt-1">
            {(["add", "multiply"] as const).map(m => (
              <label key={m} className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
                <input type="radio" name={`pm-${q.key}`} value={m} checked={q.price_mode === m} onChange={() => onChange({ ...q, price_mode: m })} />
                {m === "add" ? "Add/subtract (±$)" : "Multiply (×)"}
              </label>
            ))}
          </div>
        </div>
      )}

      {hasOptions && (
        <OptionsEditor options={q.options} onChange={opts => onChange({ ...q, options: opts })} affects_price={q.affects_price} />
      )}
    </div>
  );
}

export function IntakeSchemaBuilder({ schema, onChange }: {
  schema: IntakeSchemaJson;
  onChange: (s: IntakeSchemaJson) => void;
}) {
  const [activeTab, setActiveTab] = useState<QType>("dropdown");
  const qs = schema.questions;

  const update = (type: QType, list: IntakeQuestion[]) =>
    onChange({ ...schema, questions: { ...qs, [type]: list } });

  const addQ = (type: QType) => {
    if (qs[type].length >= MAX) return;
    update(type, [...qs[type], emptyQ(qs[type].length)]);
  };

  const moveQ = (type: QType, i: number, dir: -1 | 1) => {
    const list = [...qs[type]]; const j = i + dir;
    if (j < 0 || j >= list.length) return;
    [list[i], list[j]] = [list[j], list[i]];
    update(type, list);
  };

  const allKeys = [
    ...qs.dropdown, ...qs.multiselect, ...qs.single_line, ...qs.multi_line,
  ].map(q => q.key).filter(Boolean);

  const current = qs[activeTab];
  const tab = TABS.find(t => t.key === activeTab)!;

  return (
    <div className="space-y-3">
      <div className="flex gap-0.5 border-b border-slate-200">
        {TABS.map(t => (
          <button
            key={t.key}
            type="button"
            onClick={() => setActiveTab(t.key)}
            data-testid={`intake-tab-${t.key}`}
            className={`px-3 py-1.5 text-xs font-medium rounded-t transition-colors ${
              activeTab === t.key
                ? "bg-white border border-b-white border-slate-200 text-slate-800 -mb-px z-10"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label} <span className="ml-1 text-slate-400">({qs[t.key].length})</span>
          </button>
        ))}
      </div>

      <div className="space-y-2 min-h-[60px]">
        {current.length === 0 && (
          <p className="text-xs text-slate-400 py-3 text-center">No {tab.label.toLowerCase()} questions yet.</p>
        )}
        {current.map((q, i) => (
          <QuestionEditor
            key={i}
            q={q} idx={i} total={current.length}
            allKeys={allKeys} hasOptions={tab.hasOptions}
            onChange={q => { const list = [...current]; list[i] = q; update(activeTab, list); }}
            onRemove={() => update(activeTab, current.filter((_, j) => j !== i))}
            onMove={dir => moveQ(activeTab, i, dir)}
          />
        ))}
      </div>

      <div className="flex items-center justify-between pt-1">
        <Button
          type="button" variant="outline" size="sm"
          onClick={() => addQ(activeTab)}
          disabled={current.length >= MAX}
          data-testid={`intake-add-${activeTab}`}
        >
          <Plus size={13} className="mr-1" /> Add {tab.label} question
        </Button>
        <span className="text-xs text-slate-400">{current.length} / {MAX}</span>
      </div>
    </div>
  );
}
