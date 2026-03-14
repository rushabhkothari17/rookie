import { motion } from "framer-motion";
import { PackageOpen, FileSearch, BookOpen, ShoppingBag, Inbox, Users, FolderOpen, ClipboardList, Zap } from "lucide-react";
import { ReactNode } from "react";

const ICON_MAP: Record<string, ReactNode> = {
  orders:        <PackageOpen size={26} />,
  search:        <FileSearch size={26} />,
  articles:      <BookOpen size={26} />,
  products:      <ShoppingBag size={26} />,
  users:         <Users size={26} />,
  documents:     <FolderOpen size={26} />,
  forms:         <ClipboardList size={26} />,
  webhooks:      <Zap size={26} />,
  default:       <Inbox size={26} />,
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
      <div className="aa-empty-geo mb-3">
        <div className="absolute inset-0 flex items-center justify-center z-10"
          style={{ color: "var(--aa-accent)" }}>
          {ICON_MAP[icon]}
        </div>
      </div>
      <p className="text-[15px] font-semibold mb-1.5 mt-4 tracking-tight" style={{ color: "var(--aa-text)" }}>{title}</p>
      {description && (
        <p className="text-sm max-w-xs leading-relaxed" style={{ color: "var(--aa-muted)" }}>{description}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="mt-5 btn-primary px-5 py-2 text-sm rounded-full aa-btn-ripple font-medium"
          data-testid="empty-state-action"
        >
          {action.label}
        </button>
      )}
    </motion.div>
  );
}
