import { motion } from "framer-motion";
import { PackageOpen, FileSearch, BookOpen, ShoppingBag, Inbox } from "lucide-react";
import { ReactNode } from "react";

const ICON_MAP: Record<string, ReactNode> = {
  orders:    <PackageOpen size={32} />,
  search:    <FileSearch size={32} />,
  articles:  <BookOpen size={32} />,
  products:  <ShoppingBag size={32} />,
  default:   <Inbox size={32} />,
};

interface EmptyStateProps {
  icon?: keyof typeof ICON_MAP;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  "data-testid"?: string;
}

export function EmptyState({ icon = "default", title, description, action, "data-testid": testId }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-col items-center justify-center py-16 text-center"
      data-testid={testId}
    >
      <div
        className="h-16 w-16 rounded-2xl flex items-center justify-center mb-4 shadow-sm"
        style={{ backgroundColor: "color-mix(in srgb, var(--aa-primary) 10%, transparent)", color: "var(--aa-primary)" }}
      >
        {ICON_MAP[icon]}
      </div>
      <p className="text-[15px] font-semibold mb-1" style={{ color: "var(--aa-text)" }}>{title}</p>
      {description && (
        <p className="text-sm max-w-xs" style={{ color: "var(--aa-muted)" }}>{description}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="mt-5 btn-primary px-5 py-2 text-sm rounded-full aa-btn-ripple"
          data-testid="empty-state-action"
        >
          {action.label}
        </button>
      )}
    </motion.div>
  );
}
