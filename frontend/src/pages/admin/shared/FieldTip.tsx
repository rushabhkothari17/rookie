/**
 * FieldTip — inline ? icon with a hover tooltip.
 * Usage: <FieldTip tip="Explanation text here" />
 * Drop it inside any <label> or next to any field heading.
 */
import { HelpCircle } from "lucide-react";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";

interface Props {
  tip: string;
  side?: "top" | "right" | "bottom" | "left";
}

export function FieldTip({ tip, side = "top" }: Props) {
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex items-center cursor-help text-slate-300 hover:text-slate-500 transition-colors ml-1 align-middle">
            <HelpCircle size={13} />
          </span>
        </TooltipTrigger>
        <TooltipContent
          side={side}
          className="max-w-[280px] text-[11px] leading-relaxed bg-slate-900 text-white border-0 shadow-lg px-3 py-2"
        >
          <p>{tip}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
