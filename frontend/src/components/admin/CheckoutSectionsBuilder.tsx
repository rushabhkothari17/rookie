import { useState } from "react";
import { ChevronDown, ChevronUp, Pencil, Plus, X } from "lucide-react";
import FormSchemaBuilder from "@/components/FormSchemaBuilder";

interface CheckoutSection {
  id: string;
  title: string;
  description: string;
  enabled: boolean;
  order: number;
  fields_schema: string;
}

function makeCSId() {
  return "cs_" + Math.random().toString(36).slice(2, 8);
}

export default function CheckoutSectionsBuilder({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [sections, setSections] = useState<CheckoutSection[]>(() => {
    try {
      const p = JSON.parse(value);
      return Array.isArray(p) ? p : [];
    } catch {
      return [];
    }
  });
  const [editingId, setEditingId] = useState<string | null>(null);

  const commit = (updated: CheckoutSection[]) => {
    const reordered = updated.map((s, i) => ({ ...s, order: i }));
    setSections(reordered);
    onChange(JSON.stringify(reordered));
  };

  const add = () => {
    const id = makeCSId();
    const newSection: CheckoutSection = {
      id,
      title: "New Section",
      description: "",
      enabled: true,
      order: sections.length,
      fields_schema: "[]",
    };
    const updated = [...sections, newSection];
    commit(updated);
    setEditingId(id);
  };

  const remove = (id: string) => {
    commit(sections.filter((s) => s.id !== id));
    if (editingId === id) setEditingId(null);
  };

  const update = (id: string, patch: Partial<CheckoutSection>) => {
    commit(sections.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  };

  const move = (id: string, dir: -1 | 1) => {
    const idx = sections.findIndex((s) => s.id === id);
    if (idx < 0) return;
    const next = idx + dir;
    if (next < 0 || next >= sections.length) return;
    const arr = [...sections];
    [arr[idx], arr[next]] = [arr[next], arr[idx]];
    commit(arr);
  };

  return (
    <div className="space-y-2" data-testid="checkout-sections-builder">
      {sections.length === 0 && (
        <p className="text-xs text-slate-400 text-center py-6 border border-dashed border-slate-200 rounded-lg">
          No custom sections yet. Add your first section below.
          <br />
          <span className="text-slate-300">Legacy sections (Zoho/Partner) remain active until you add sections here.</span>
        </p>
      )}

      {sections.map((section, idx) => (
        <div
          key={section.id}
          className="rounded-xl border border-slate-200 bg-white overflow-hidden"
          data-testid={`checkout-section-card-${section.id}`}
        >
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className={`h-2 w-2 rounded-full flex-shrink-0 ${section.enabled ? "bg-green-500" : "bg-slate-300"}`} />
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{section.title || "Untitled"}</p>
                {section.description && (
                  <p className="text-xs text-slate-400 truncate max-w-xs">{section.description}</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                onClick={() => update(section.id, { enabled: !section.enabled })}
                className={`px-2.5 py-1 text-xs font-medium rounded-full transition-all border ${
                  section.enabled
                    ? "bg-green-50 text-green-700 border-green-200"
                    : "bg-slate-100 text-slate-500 border-slate-200"
                }`}
                data-testid={`checkout-section-toggle-${section.id}`}
              >
                {section.enabled ? "Visible" : "Hidden"}
              </button>
              <button
                onClick={() => move(section.id, -1)}
                disabled={idx === 0}
                className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30"
              >
                <ChevronUp size={14} />
              </button>
              <button
                onClick={() => move(section.id, 1)}
                disabled={idx === sections.length - 1}
                className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30"
              >
                <ChevronDown size={14} />
              </button>
              <button
                onClick={() => setEditingId(editingId === section.id ? null : section.id)}
                className={`p-1.5 rounded-lg transition-colors ${
                  editingId === section.id
                    ? "bg-slate-900 text-white"
                    : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                }`}
                data-testid={`checkout-section-edit-${section.id}`}
              >
                <Pencil size={13} />
              </button>
              <button
                onClick={() => remove(section.id)}
                className="p-1.5 rounded-lg text-red-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                data-testid={`checkout-section-remove-${section.id}`}
              >
                <X size={13} />
              </button>
            </div>
          </div>

          {editingId === section.id && (
            <div className="border-t border-slate-100 p-4 space-y-4 bg-slate-50">
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-slate-500 block mb-1">Section Title</label>
                  <input
                    value={section.title}
                    onChange={(e) => update(section.id, { title: e.target.value })}
                    className="w-full h-9 text-sm border border-slate-200 rounded-lg px-3 bg-white"
                    placeholder="e.g. Account Details"
                    data-testid={`checkout-section-title-input-${section.id}`}
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500 block mb-1">
                    Description <span className="text-slate-400">(shown to customers above the fields)</span>
                  </label>
                  <textarea
                    value={section.description}
                    onChange={(e) => update(section.id, { description: e.target.value })}
                    className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white resize-none"
                    rows={2}
                    placeholder="Optional description shown above the form fields"
                    data-testid={`checkout-section-desc-input-${section.id}`}
                  />
                </div>
              </div>
              <div className="border-t border-slate-100 pt-4">
                <FormSchemaBuilder
                  title="Section Fields"
                  value={section.fields_schema}
                  onChange={(v) => update(section.id, { fields_schema: v })}
                />
              </div>
            </div>
          )}
        </div>
      ))}

      <button
        onClick={add}
        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 font-medium px-3 py-2 rounded-lg hover:bg-blue-50 transition-colors mt-1"
        data-testid="add-checkout-section-btn"
      >
        <Plus size={14} /> Add Section
      </button>
    </div>
  );
}
