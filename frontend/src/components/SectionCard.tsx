export default function SectionCard({
  title,
  children,
  testId,
}: {
  title: string;
  children: React.ReactNode;
  testId: string;
}) {
  return (
    <div
      className="rounded-3xl bg-white/80 p-6 shadow-[0_16px_40px_rgba(15,23,42,0.08)] backdrop-blur"
      data-testid={testId}
    >
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <div className="mt-3 text-sm text-slate-600">{children}</div>
    </div>
  );
}
