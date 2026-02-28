/**
 * FieldTip — inline ? icon with a click-to-toggle tooltip.
 * Opens on click, closes on second click or when clicking outside.
 * Usage: <FieldTip tip="Explanation text here" />
 */
import { HelpCircle } from "lucide-react";
import { useState, useEffect, useRef } from "react";

interface Props {
  tip: string;
  side?: "top" | "right" | "bottom" | "left";
}

export function FieldTip({ tip, side = "top" }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const positionCls =
    side === "top"
      ? "bottom-full left-1/2 -translate-x-1/2 mb-2"
      : side === "bottom"
      ? "top-full left-1/2 -translate-x-1/2 mt-2"
      : side === "right"
      ? "left-full top-1/2 -translate-y-1/2 ml-2"
      : "right-full top-1/2 -translate-y-1/2 mr-2";

  return (
    <span
      ref={ref}
      className="relative inline-flex items-center cursor-pointer ml-1 align-middle"
      data-testid="field-tip"
      onClick={e => { e.preventDefault(); e.stopPropagation(); setOpen(v => !v); }}
    >
      <HelpCircle
        size={13}
        className={`transition-colors ${open ? "text-slate-600" : "text-slate-300 hover:text-slate-500"}`}
      />
      {open && (
        <span
          className={`
            absolute ${positionCls} w-64 z-[9999]
            bg-slate-900 text-white text-[11px] leading-relaxed
            px-3 py-2 rounded shadow-lg
            pointer-events-none whitespace-normal
          `}
        >
          {tip}
        </span>
      )}
    </span>
  );
}

