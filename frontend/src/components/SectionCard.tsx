import { ReactNode } from "react";
import * as icons from "lucide-react";

const COLOR_MAP: Record<string, string> = {
  blue: "text-blue-500",
  green: "text-green-500",
  red: "text-red-500",
  purple: "text-purple-500",
  orange: "text-orange-500",
  slate: "text-slate-500",
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
  const iconClass = iconColor ? (COLOR_MAP[iconColor] || "text-blue-500") : "text-blue-500";

  return (
    <div
      className="rounded-2xl border border-slate-100 bg-white px-6 pt-6 pb-8 shadow-sm"
      data-testid={testId}
    >
      <div className="mb-5 flex items-center gap-3">
        {IconComp ? (
          <IconComp size={16} className={`flex-shrink-0 ${iconClass}`} />
        ) : (
          <div className="h-5 w-1 flex-shrink-0 rounded-full bg-red-500" />
        )}
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">{title}</h3>
      </div>
      <div className="text-sm text-slate-600 leading-relaxed">{children}</div>
    </div>
  );
}
