import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Lock, Trash2, ChevronUp, ChevronDown, Plus, Settings2, GripVertical } from "lucide-react";

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
}

export type FieldType = "text" | "email" | "tel" | "number" | "date" | "textarea" | "select" | "checkbox" | "file" | "password";

const FIELD_TYPES: { value: FieldType; label: string }[] = [
  { value: "text", label: "Text" },
  { value: "email", label: "Email" },
  { value: "tel", label: "Phone" },
  { value: "number", label: "Number" },
  { value: "date", label: "Date" },
  { value: "textarea", label: "Textarea" },
  { value: "select", label: "Dropdown" },
  { value: "checkbox", label: "Checkbox" },
  { value: "file", label: "File Upload" },
  { value: "password", label: "Password" },
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
    parseSchema(value).sort((a, b) => a.order - b.order)
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
    commit(fields.filter(f => f.id !== id));
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
      return updated;
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
                  {field.locked && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${field.enabled ? "text-emerald-700 bg-emerald-50" : "text-slate-400 bg-slate-100"}`}>
                      {field.enabled ? "shown" : "hidden"}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 font-mono">{field.key}</p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {field.locked && (
                  <button
                    type="button"
                    onClick={() => toggle(field.id, "enabled", !field.enabled)}
                    className={`text-xs px-2 py-1 rounded transition-colors ${field.enabled ? "bg-slate-100 text-slate-600 hover:bg-slate-200" : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"}`}
                    data-testid={`field-toggle-${field.id}`}
                  >
                    {field.enabled ? "Hide" : "Show"}
                  </button>
                )}
                <button type="button" onClick={() => move(field.id, -1)} disabled={idx === 0} className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30">
                  <ChevronUp size={14} />
                </button>
                <button type="button" onClick={() => move(field.id, 1)} disabled={idx === fields.length - 1} className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30">
                  <ChevronDown size={14} />
                </button>
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
                <div>
                  <label className="text-[11px] text-slate-500 font-medium">Label</label>
                  <Input value={field.label} onChange={e => updateField(field.id, { label: e.target.value })} className="mt-0.5 h-7 text-xs" />
                </div>
                <div>
                  <label className="text-[11px] text-slate-500 font-medium">Field type</label>
                  <Select value={field.type} onValueChange={v => updateField(field.id, { type: v as FieldType, options: [] })}>
                    <SelectTrigger className="mt-0.5 h-7 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {FIELD_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-[11px] text-slate-500 font-medium">Placeholder</label>
                  <Input value={field.placeholder} onChange={e => updateField(field.id, { placeholder: e.target.value })} className="mt-0.5 h-7 text-xs" />
                </div>
                <div className="flex items-end gap-4 pb-1">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input type="checkbox" checked={field.required} onChange={e => updateField(field.id, { required: e.target.checked })} className="w-3.5 h-3.5" />
                    <span className="text-xs text-slate-600">Required</span>
                  </label>
                </div>
                {field.type === "select" && (
                  <div className="col-span-2">
                    <label className="text-[11px] text-slate-500 font-medium">Options (one per line, format: Label|value)</label>
                    <Textarea
                      value={
                        Array.isArray(field.options) 
                          ? field.options.join("\n") 
                          : (field.options || "")
                      }
                      onChange={e => updateField(field.id, { options: e.target.value.split("\n").filter(Boolean) })}
                      rows={3}
                      className="mt-0.5 text-xs font-mono"
                      placeholder="Option One|opt_1&#10;Option Two|opt_2"
                    />
                  </div>
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
