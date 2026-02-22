import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { X, Plus, ChevronUp, ChevronDown } from "lucide-react";
import * as LucideIcons from "lucide-react";
import { IconPicker } from "@/components/IconPicker";

export interface CustomSection {
  id: string;
  name: string;
  content: string;
  icon: string;
  icon_color: string;
  tags: string[];
  order: number;
}

export const SECTION_ICONS = [
  "FileText", "CheckCircle", "Zap", "Shield", "Star", "Clock",
  "Settings", "Users", "BarChart", "Globe", "Lock", "Search",
  "Headphones", "Rocket", "Target", "Award", "Briefcase", "Code",
  "Database", "Heart", "TrendingUp", "Layers", "Package", "Box",
];

export const ICON_COLORS = [
  { value: "blue", hex: "#3b82f6" },
  { value: "green", hex: "#22c55e" },
  { value: "red", hex: "#ef4444" },
  { value: "purple", hex: "#a855f7" },
  { value: "orange", hex: "#f97316" },
  { value: "slate", hex: "#64748b" },
];

export const COLOR_HEX: Record<string, string> = Object.fromEntries(
  ICON_COLORS.map(c => [c.value, c.hex])
);

const MAX_SECTIONS = 10;

function makeId() {
  return Math.random().toString(36).substr(2, 9);
}

function DynamicIcon({ name, colorHex }: { name: string; colorHex?: string }) {
  const IconComp = (LucideIcons as any)[name];
  if (!IconComp) return null;
  return <IconComp size={15} style={{ color: colorHex || "#3b82f6" }} />;
}

export const DEFAULT_SECTION: CustomSection = {
  id: "",
  name: "Overview",
  content: "",
  icon: "FileText",
  icon_color: "blue",
  tags: [],
  order: 0,
};

export function SectionsEditor({
  sections,
  onChange,
}: {
  sections: CustomSection[];
  onChange: (sections: CustomSection[]) => void;
}) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(sections.length > 0 ? 0 : null);

  const add = () => {
    if (sections.length >= MAX_SECTIONS) return;
    const newSection: CustomSection = { ...DEFAULT_SECTION, id: makeId(), order: sections.length };
    onChange([...sections, newSection]);
    setExpandedIdx(sections.length);
  };

  const remove = (i: number) => {
    const next = sections.filter((_, j) => j !== i).map((s, j) => ({ ...s, order: j }));
    onChange(next);
    setExpandedIdx(null);
  };

  const update = (i: number, changes: Partial<CustomSection>) => {
    const next = [...sections];
    next[i] = { ...next[i], ...changes };
    onChange(next);
  };

  const move = (i: number, dir: -1 | 1) => {
    const next = [...sections];
    const j = i + dir;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    next.forEach((s, idx) => { s.order = idx; });
    onChange(next);
    setExpandedIdx(j);
  };

  const addTag = (i: number) => update(i, { tags: [...sections[i].tags, ""] });
  const updateTag = (i: number, ti: number, v: string) => {
    const tags = [...sections[i].tags];
    tags[ti] = v;
    update(i, { tags });
  };
  const removeTag = (i: number, ti: number) => {
    update(i, { tags: sections[i].tags.filter((_, j) => j !== ti) });
  };

  return (
    <div className="space-y-2">
      {sections.length === 0 && (
        <p className="text-xs text-slate-400 text-center py-4 border border-dashed border-slate-200 rounded-lg">
          No page sections yet. Add your first section below.
        </p>
      )}

      {sections.map((sec, i) => {
        const isExpanded = expandedIdx === i;

        return (
          <div key={sec.id || i} className="border border-slate-200 rounded-lg bg-white overflow-hidden">
            {/* Section header row */}
            <div
              className="flex items-center gap-2 px-3 py-2.5 cursor-pointer select-none hover:bg-slate-50 transition-colors"
              onClick={() => setExpandedIdx(isExpanded ? null : i)}
              data-testid={`section-header-${i}`}
            >
              <DynamicIcon name={sec.icon || "FileText"} colorHex={COLOR_HEX[sec.icon_color] || "#3b82f6"} />
              <span className="flex-1 text-sm font-medium text-slate-700 truncate">
                {sec.name || <span className="text-slate-400 italic">Untitled section</span>}
              </span>
              <span className="text-[10px] text-slate-400 shrink-0">{isExpanded ? "▲" : "▼"}</span>
              <div className="flex items-center gap-0.5 ml-1 shrink-0" onClick={e => e.stopPropagation()}>
                <button type="button" onClick={() => move(i, -1)} disabled={i === 0} className="p-0.5 text-slate-400 hover:text-slate-700 disabled:opacity-25" title="Move up"><ChevronUp size={13} /></button>
                <button type="button" onClick={() => move(i, 1)} disabled={i === sections.length - 1} className="p-0.5 text-slate-400 hover:text-slate-700 disabled:opacity-25" title="Move down"><ChevronDown size={13} /></button>
                <button type="button" onClick={() => remove(i)} className="p-0.5 text-red-400 hover:text-red-600 ml-0.5" data-testid={`section-remove-${i}`}><X size={13} /></button>
              </div>
            </div>

            {/* Expanded editor */}
            {isExpanded && (
              <div className="px-3 pb-3 space-y-3 border-t border-slate-100 pt-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] text-slate-500">Section Name *</label>
                    <Input
                      value={sec.name}
                      onChange={e => update(i, { name: e.target.value })}
                      placeholder="e.g. What's Included"
                      className="h-7 text-xs mt-0.5"
                      data-testid={`section-name-${i}`}
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-500">Icon</label>
                    <div className="mt-0.5">
                      <IconPicker
                        value={sec.icon || "FileText"}
                        onChange={v => update(i, { icon: v })}
                        colorHex={COLOR_HEX[sec.icon_color] || "#64748b"}
                      />
                    </div>
                  </div>
                </div>

                {/* Icon color swatches */}
                <div>
                  <label className="text-[11px] text-slate-500">Icon Color</label>
                  <div className="flex gap-2 mt-1">
                    {ICON_COLORS.map(c => (
                      <button
                        key={c.value}
                        type="button"
                        onClick={() => update(i, { icon_color: c.value })}
                        className={`w-5 h-5 rounded-full transition-all border-2 ${
                          sec.icon_color === c.value ? "border-slate-700 scale-110" : "border-slate-200 opacity-70"
                        }`}
                        style={{ backgroundColor: c.hex }}
                        title={c.value}
                        data-testid={`section-color-${i}-${c.value}`}
                      />
                    ))}
                  </div>
                </div>

                {/* Content */}
                <div>
                  <label className="text-[11px] text-slate-500">Content (Markdown supported)</label>
                  <Textarea
                    value={sec.content}
                    onChange={e => update(i, { content: e.target.value })}
                    placeholder="Describe this section… Use markdown for formatting."
                    rows={5}
                    className="mt-0.5 text-xs font-mono"
                    data-testid={`section-content-${i}`}
                  />
                </div>

                {/* Tags */}
                <div>
                  <label className="text-[11px] text-slate-500">Tags (optional)</label>
                  <div className="space-y-1 mt-1">
                    {sec.tags.map((tag, ti) => (
                      <div key={ti} className="flex gap-1.5 items-center">
                        <Input
                          value={tag}
                          onChange={e => updateTag(i, ti, e.target.value)}
                          placeholder="e.g. Included"
                          className="h-6 text-xs flex-1"
                          data-testid={`section-tag-${i}-${ti}`}
                        />
                        <button type="button" onClick={() => removeTag(i, ti)} className="text-red-400 hover:text-red-600 shrink-0">
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                    <Button type="button" variant="outline" size="sm" onClick={() => addTag(i)} className="h-6 text-xs px-2">
                      <Plus size={11} className="mr-1" /> Tag
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}

      <div className="flex items-center justify-between pt-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={add}
          disabled={sections.length >= MAX_SECTIONS}
          data-testid="sections-add-btn"
        >
          <Plus size={13} className="mr-1" /> Add Section
        </Button>
        <span className="text-xs text-slate-400">{sections.length} / {MAX_SECTIONS}</span>
      </div>
    </div>
  );
}
