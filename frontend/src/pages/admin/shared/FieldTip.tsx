/**
 * FieldTip — inline ? icon with a CSS hover tooltip.
 * Pure Tailwind implementation — no Radix UI dependency.
 * Usage: <FieldTip tip="Explanation text here" />
 * Drop it inside any <label> or next to any field heading.
 */
import { HelpCircle } from "lucide-react";

interface Props {
  tip: string;
  side?: "top" | "right" | "bottom" | "left";
}

export function FieldTip({ tip, side = "top" }: Props) {
  const positionCls =
    side === "top"
      ? "bottom-full left-1/2 -translate-x-1/2 mb-2"
      : side === "bottom"
      ? "top-full left-1/2 -translate-x-1/2 mt-2"
      : side === "right"
      ? "left-full top-1/2 -translate-y-1/2 ml-2"
      : "right-full top-1/2 -translate-y-1/2 mr-2"; // left

  return (
    <span
      className="relative inline-flex items-center cursor-help group ml-1 align-middle"
      data-testid="field-tip"
    >
      <HelpCircle
        size={13}
        className="text-slate-300 group-hover:text-slate-500 transition-colors"
      />
      <span
        className={`
          absolute ${positionCls} w-64 z-50
          bg-slate-900 text-white text-[11px] leading-relaxed
          px-3 py-2 rounded shadow-lg
          invisible opacity-0
          group-hover:visible group-hover:opacity-100
          transition-opacity duration-150
          pointer-events-none whitespace-normal
        `}
      >
        {tip}
      </span>
    </span>
  );
}
