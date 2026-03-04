import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface RequiredLabelProps {
  children: ReactNode;
  className?: string;
  /** Extra hint shown after the asterisk in slate-400 (e.g. "required for Scope - Final") */
  hint?: string;
  /** Elements rendered after the asterisk (e.g. <FieldTip />) */
  trailing?: ReactNode;
}

/**
 * Renders a form label with a consistent red asterisk for required fields.
 *
 * Usage:
 *   <RequiredLabel>Field Name</RequiredLabel>
 *   <RequiredLabel hint="required for Scope - Final">Price</RequiredLabel>
 *   <RequiredLabel trailing={<FieldTip tip="..." />}>Billing type</RequiredLabel>
 */
export function RequiredLabel({ children, className, hint, trailing }: RequiredLabelProps) {
  return (
    <label className={cn("text-xs font-medium text-slate-700", className)}>
      {children}{" "}
      <span className="text-red-500">*</span>
      {trailing && <>{" "}{trailing}</>}
      {hint && <span className="text-slate-400 font-normal"> ({hint})</span>}
    </label>
  );
}
