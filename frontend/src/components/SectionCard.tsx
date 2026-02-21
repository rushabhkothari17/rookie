import { ReactNode } from "react";

export default function SectionCard({
  title,
  children,
  testId,
}: {
  title: string;
  children: ReactNode;
  testId: string;
}) {
  return (
    <div
      className="rounded-2xl border border-slate-100 bg-white px-6 pt-6 pb-8 shadow-sm"
      data-testid={testId}
    >
      <div className="mb-5 flex items-center gap-3">
        <div className="h-5 w-1 flex-shrink-0 rounded-full bg-red-500" />
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">{title}</h3>
      </div>
      <div className="text-sm text-slate-600 leading-relaxed">{children}</div>
    </div>
  );
}
