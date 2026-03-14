interface AdminPageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export function AdminPageHeader({ title, subtitle, actions }: AdminPageHeaderProps) {
  return (
    <div className="aa-page-header anim-in">
      <div>
        <h2 className="text-xl font-bold tracking-tight aa-gradient-title">{title}</h2>
        {subtitle && (
          <p className="text-sm mt-1 flex items-center gap-1.5" style={{ color: "var(--aa-muted)" }}>
            <span
              className="inline-block w-1.5 h-1.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: "var(--aa-accent)" }}
            />
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>
      )}
    </div>
  );
}
