import { ReactNode } from "react";
import * as icons from "lucide-react";

const COLOR_HEX: Record<string, string> = {
  blue: "#3b82f6",
  green: "#22c55e",
  red: "#ef4444",
  purple: "#a855f7",
  orange: "#f97316",
  slate: "#64748b",
};

export default function SectionCard({
  title,
  children,
  testId,
  icon,
  iconColor,
}: {
  title: string;
  children: ReactNode;
  testId: string;
  icon?: string;
  iconColor?: string;
}) {
  const IconComp = icon ? (icons as any)[icon] : null;
  const iconHex = iconColor ? (COLOR_HEX[iconColor] || "#3b82f6") : "#3b82f6";

  return (
    <div
      className="rounded-2xl border border-slate-100 bg-white px-6 pt-6 pb-8 shadow-sm"
      data-testid={testId}
    >
      <div className="mb-5 flex items-center gap-3">
        {IconComp ? (
          <IconComp size={16} style={{ color: iconHex }} className="flex-shrink-0" />
        ) : (
          <div className="h-5 w-1 flex-shrink-0 rounded-full bg-red-500" />
        )}
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">{title}</h3>
      </div>
      <div className="text-sm text-slate-600 leading-relaxed">{children}</div>
    </div>
  );
}
