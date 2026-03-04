import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface RequiredLabelProps {
  children: ReactNode;
  className?: string;
  /** Extra hint shown after the asterisk (e.g. "required for Scope - Final") */
  hint?: string;
}

/**
 * Renders a form label with a consistent red asterisk for required fields.
 *
 * Usage:
 *   <RequiredLabel>Field Name</RequiredLabel>
 *   // → Field Name <span class="text-red-500">*</span>
 *
 *   <RequiredLabel hint="required for Scope - Final">Price</RequiredLabel>
 *   // → Price <span class="text-red-500">*</span> <span class="text-slate-400">(required for Scope - Final)</span>
 */
export function RequiredLabel({ children, className, hint }: RequiredLabelProps) {
  return (
    <label className={cn("text-xs font-medium text-slate-700", className)}>
      {children}{" "}
      <span className="text-red-500">*</span>
      {hint && <span className="text-slate-400 font-normal"> ({hint})</span>}
    </label>
  );
}
