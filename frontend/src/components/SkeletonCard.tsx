import { motion } from "framer-motion";

/** Shimmer skeleton card — use during loading states */
export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-200 overflow-hidden aa-skeleton-card ${className}`}
      style={{ backgroundColor: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
      <div className="aa-shimmer h-36 w-full" />
      <div className="p-4 space-y-2.5">
        <div className="aa-shimmer h-4 rounded-full w-3/4" />
        <div className="aa-shimmer h-3 rounded-full w-1/2" />
        <div className="aa-shimmer h-3 rounded-full w-2/3" />
        <div className="mt-4 flex items-center justify-between">
          <div className="aa-shimmer h-5 rounded-full w-16" />
          <div className="aa-shimmer h-7 rounded-lg w-24" />
        </div>
      </div>
    </div>
  );
}

/** Shimmer skeleton row — use for table loading states */
export function SkeletonRow({ cols = 5 }: { cols?: number }) {
  return (
    <tr className="border-b" style={{ borderColor: "var(--aa-border)" }}>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="aa-shimmer h-3.5 rounded-full" style={{ width: `${55 + (i % 3) * 20}%` }} />
        </td>
      ))}
    </tr>
  );
}

/** Shimmer skeleton stat card */
export function SkeletonStat() {
  return (
    <div className="rounded-xl p-4 space-y-2 border" style={{ backgroundColor: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
      <div className="aa-shimmer h-3 rounded-full w-16" />
      <div className="aa-shimmer h-7 rounded-lg w-12" />
    </div>
  );
}

/** Grid of skeleton cards */
export function SkeletonGrid({ count = 6, cols = "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3" }: { count?: number; cols?: string }) {
  return (
    <motion.div
      className={`grid gap-5 ${cols}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </motion.div>
  );
}
