import { useState } from "react";
import { ChevronDown } from "lucide-react";
import * as LucideIcons from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export const ALL_SECTION_ICONS = [
  "FileText", "CheckCircle", "Zap", "Shield", "Star", "Clock",
  "Settings", "Users", "BarChart", "Globe", "Lock", "Search",
  "Headphones", "Rocket", "Target", "Award", "Briefcase", "Code",
  "Database", "Heart", "TrendingUp", "Layers", "Package", "Box",
  "Bell", "Calendar", "Camera", "Flag", "Gift", "Laptop",
  "Mail", "Map", "Phone", "Smile", "Tag", "Truck", "Wrench",
];

function DynamicIcon({ name, colorHex }: { name: string; colorHex?: string }) {
  const IconComp = (LucideIcons as any)[name];
  if (!IconComp) return <span className="w-4 h-4" />;
  return <IconComp size={16} style={{ color: colorHex || "#64748b" }} />;
}

export function IconPicker({
  value,
  onChange,
  colorHex,
}: {
  value: string;
  onChange: (icon: string) => void;
  colorHex?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-2 h-8 px-3 border border-slate-200 rounded bg-white hover:bg-slate-50 text-xs text-slate-600 min-w-[120px]"
          data-testid="icon-picker-trigger"
        >
          <DynamicIcon name={value || "FileText"} colorHex={colorHex} />
          <span className="flex-1 text-left truncate">{value || "FileText"}</span>
          <ChevronDown size={12} className="text-slate-400 shrink-0" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="w-72 p-3"
        align="start"
        side="bottom"
        data-testid="icon-picker-popup"
      >
        <p className="text-[11px] text-slate-400 font-medium mb-2 uppercase tracking-wide">Select an icon</p>
        <div className="grid grid-cols-7 gap-1 max-h-52 overflow-y-auto">
          {ALL_SECTION_ICONS.map(name => (
            <button
              key={name}
              type="button"
              onClick={() => { onChange(name); setOpen(false); }}
              title={name}
              className={`p-1.5 rounded hover:bg-slate-100 flex items-center justify-center transition-colors ${
                value === name ? "bg-slate-100 ring-1 ring-slate-400" : ""
              }`}
              data-testid={`icon-option-${name}`}
            >
              <DynamicIcon name={name} colorHex={colorHex || "#64748b"} />
            </button>
          ))}
        </div>
        {value && (
          <p className="text-[11px] text-slate-400 text-center mt-2 pt-2 border-t border-slate-100">
            Selected: <span className="font-medium text-slate-600">{value}</span>
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}
