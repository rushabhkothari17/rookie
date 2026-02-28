import { useState, useEffect } from "react";
import api from "@/lib/api";
import { AlertTriangle, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

type UsageEntry = {
  current: number;
  limit: number | null;
  pct: number;
  warning: boolean;
  blocked: boolean;
};

type Snapshot = {
  usage: Record<string, UsageEntry>;
};

export function LimitBanner() {
  const { user } = useAuth();
  const [dismissed, setDismissed] = useState(false);
  const [blockedResources, setBlockedResources] = useState<string[]>([]);
  const [warningResources, setWarningResources] = useState<string[]>([]);

  // Only show for partner admins (not platform_admin)
  const isPartner = user?.role && !["platform_admin"].includes(user.role);

  useEffect(() => {
    if (!isPartner) return;
    api.get("/admin/usage")
      .then(({ data }: { data: Snapshot }) => {
        const blocked: string[] = [];
        const warning: string[] = [];
        Object.entries(data.usage || {}).forEach(([key, entry]) => {
          if (entry.limit === null) return;
          if (entry.blocked) blocked.push(key);
          else if (entry.warning) warning.push(key);
        });
        setBlockedResources(blocked);
        setWarningResources(warning);
      })
      .catch(() => {});
  }, [isPartner]);

  if (!isPartner || dismissed) return null;
  if (blockedResources.length === 0 && warningResources.length === 0) return null;

  const isBlocked = blockedResources.length > 0;

  return (
    <div
      className={`flex items-center gap-3 px-4 py-2.5 text-sm ${
        isBlocked
          ? "bg-red-50 border-b border-red-200 text-red-700"
          : "bg-amber-50 border-b border-amber-200 text-amber-700"
      }`}
      data-testid="limit-banner"
    >
      <AlertTriangle className="h-4 w-4 shrink-0" />
      <span className="flex-1">
        {isBlocked ? (
          <>
            <strong>Resource limit reached</strong> — some actions are blocked.{" "}
            Contact your administrator to upgrade your plan.
          </>
        ) : (
          <>
            <strong>Approaching resource limits</strong> — you are near your plan's limits.{" "}
            Contact your administrator if you need more capacity.
          </>
        )}
      </span>
      <button
        onClick={() => setDismissed(true)}
        className="shrink-0 hover:opacity-70"
        data-testid="dismiss-limit-banner"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
