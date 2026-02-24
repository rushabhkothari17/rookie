import { useState } from "react";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { 
  Link2, Link2Off, RefreshCw, CheckCircle, XCircle, Clock, Loader2, AlertCircle, ExternalLink
} from "lucide-react";

interface OAuthIntegrationProps {
  provider: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  status: "connected" | "connecting" | "not_connected" | "failed" | "expired";
  connectedAt?: string;
  lastRefresh?: string;
  expiresAt?: string;
  errorMessage?: string;
  canConnect: boolean;
  onStatusChange?: () => void;
}

const statusConfig: Record<string, { icon: any; color: string; bg: string; border: string; label: string; animate?: boolean }> = {
  connected: { icon: CheckCircle, color: "text-emerald-500", bg: "bg-emerald-50", border: "border-emerald-200", label: "Connected" },
  connecting: { icon: Loader2, color: "text-blue-500", bg: "bg-blue-50", border: "border-blue-200", label: "Connecting...", animate: true },
  not_connected: { icon: Link2Off, color: "text-slate-400", bg: "bg-slate-50", border: "border-slate-200", label: "Not Connected" },
  failed: { icon: XCircle, color: "text-red-500", bg: "bg-red-50", border: "border-red-200", label: "Failed" },
  expired: { icon: AlertCircle, color: "text-amber-500", bg: "bg-amber-50", border: "border-amber-200", label: "Expired" },
};

export function OAuthIntegrationTile({
  provider,
  name,
  description,
  icon,
  status,
  connectedAt,
  lastRefresh,
  expiresAt,
  errorMessage,
  canConnect,
  onStatusChange,
}: OAuthIntegrationProps) {
  const [connecting, setConnecting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  const config = statusConfig[status] || statusConfig.not_connected;
  const StatusIcon = config.icon;

  const handleConnect = async () => {
    setConnecting(true);
    try {
      const res = await api.get(`/oauth/${provider}/connect`);
      const { authorization_url } = res.data;
      
      // Open OAuth popup
      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;
      
      const popup = window.open(
        authorization_url,
        `oauth_${provider}`,
        `width=${width},height=${height},left=${left},top=${top},popup=1`
      );
      
      // Poll for popup close or success
      const pollInterval = setInterval(() => {
        try {
          if (popup?.closed) {
            clearInterval(pollInterval);
            setConnecting(false);
            onStatusChange?.();
          }
        } catch {
          // Cross-origin error - popup still open
        }
      }, 500);
      
      // Also check URL params on this page (callback redirects here)
      setTimeout(() => {
        clearInterval(pollInterval);
        setConnecting(false);
        onStatusChange?.();
      }, 60000); // Timeout after 60s
      
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to start OAuth flow");
      setConnecting(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.post(`/oauth/${provider}/refresh`);
      toast.success("Connection refreshed");
      onStatusChange?.();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to refresh token");
    } finally {
      setRefreshing(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm(`Disconnect ${name}? This will remove the integration.`)) return;
    setDisconnecting(true);
    try {
      await api.delete(`/oauth/${provider}/disconnect`);
      toast.success(`${name} disconnected`);
      onStatusChange?.();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to disconnect");
    } finally {
      setDisconnecting(false);
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return null;
    try {
      return new Date(dateStr).toLocaleDateString("en-GB", { 
        day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" 
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div
      className={`rounded-xl border p-4 ${config.bg} ${config.border}`}
      data-testid={`oauth-integration-${provider}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-white border border-slate-200 shadow-sm">
            {icon}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <p className="font-medium text-slate-800">{name}</p>
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${config.color} bg-white border ${config.border}`}>
                <StatusIcon size={10} className={config.animate ? "animate-spin" : ""} />
                {config.label}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">{description}</p>
            
            {/* Connection details */}
            {status === "connected" && (
              <div className="text-[10px] text-slate-400 mt-2 space-y-0.5">
                {connectedAt && <div>Connected: {formatDate(connectedAt)}</div>}
                {lastRefresh && <div>Last refreshed: {formatDate(lastRefresh)}</div>}
              </div>
            )}
            
            {/* Error message */}
            {errorMessage && (
              <div className="text-[10px] text-red-500 mt-2">
                Error: {errorMessage}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {status === "connected" || status === "expired" ? (
            <>
              <Button
                variant="outline"
                size="sm"
                className="h-8 px-2 text-xs"
                onClick={handleRefresh}
                disabled={refreshing}
                data-testid={`oauth-refresh-${provider}`}
              >
                <RefreshCw size={12} className={`mr-1 ${refreshing ? "animate-spin" : ""}`} />
                Refresh
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 px-2 text-xs text-red-500 hover:text-red-600 hover:bg-red-50"
                onClick={handleDisconnect}
                disabled={disconnecting}
                data-testid={`oauth-disconnect-${provider}`}
              >
                <Link2Off size={12} className="mr-1" />
                Disconnect
              </Button>
            </>
          ) : status === "connecting" ? (
            <span className="text-xs text-blue-500 flex items-center gap-1">
              <Loader2 size={14} className="animate-spin" />
              Awaiting authorization...
            </span>
          ) : (
            <Button
              variant="default"
              size="sm"
              className="h-8 px-3 text-xs"
              onClick={handleConnect}
              disabled={!canConnect || connecting}
              data-testid={`oauth-connect-${provider}`}
            >
              {connecting ? (
                <><Loader2 size={12} className="mr-1 animate-spin" /> Connecting...</>
              ) : (
                <><Link2 size={12} className="mr-1" /> Connect</>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
