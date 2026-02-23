import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Globe, Plus, Trash2, Info, ExternalLink, CheckCircle, AlertCircle, Copy } from "lucide-react";

export function CustomDomainsSection() {
  const [domains, setDomains] = useState<string[]>([]);
  const [newDomain, setNewDomain] = useState("");
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    loadDomains();
  }, []);

  const loadDomains = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/custom-domains");
      setDomains(res.data.domains || []);
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
  };

  const addDomain = async () => {
    if (!newDomain.trim()) {
      toast.error("Please enter a domain");
      return;
    }
    
    setAdding(true);
    try {
      const res = await api.put("/admin/custom-domains", {
        domains: [...domains, newDomain.trim().toLowerCase()]
      });
      setDomains(res.data.domains);
      setNewDomain("");
      toast.success("Domain added successfully");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to add domain");
    } finally {
      setAdding(false);
    }
  };

  const removeDomain = async (domain: string) => {
    if (!confirm(`Remove ${domain}?`)) return;
    
    try {
      await api.delete(`/admin/custom-domains/${encodeURIComponent(domain)}`);
      setDomains(domains.filter(d => d !== domain));
      toast.success("Domain removed");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to remove domain");
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  // Get platform URL for CNAME
  const platformUrl = process.env.REACT_APP_BACKEND_URL?.replace("https://", "").replace("http://", "").split("/")[0] || "your-platform.com";

  return (
    <div className="space-y-4" data-testid="custom-domains-section">
      {/* Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
        <div className="flex items-start gap-2">
          <Info size={14} className="text-blue-500 mt-0.5 shrink-0" />
          <div className="text-xs text-blue-700 space-y-1">
            <p className="font-medium">Custom Domain Setup</p>
            <p>
              Allow customers to access your portal via your own domain (e.g., billing.yourcompany.com).
              Customers won't need to enter a partner code when logging in from your custom domain.
            </p>
          </div>
        </div>
      </div>

      {/* DNS Instructions */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
        <p className="text-xs font-medium text-slate-700 mb-2">DNS Configuration</p>
        <div className="flex items-center gap-2 bg-white rounded border border-slate-200 px-3 py-2">
          <code className="text-xs text-slate-600 flex-1">
            CNAME → <span className="font-semibold">{platformUrl}</span>
          </code>
          <Button 
            variant="ghost" 
            size="sm" 
            className="h-6 w-6 p-0"
            onClick={() => copyToClipboard(platformUrl)}
          >
            <Copy size={12} />
          </Button>
        </div>
        <p className="text-[10px] text-slate-400 mt-2">
          Add this CNAME record in your DNS provider for each custom domain
        </p>
      </div>

      {/* Current Domains */}
      <div>
        <p className="text-xs font-medium text-slate-700 mb-2">Your Custom Domains</p>
        
        {loading ? (
          <div className="text-xs text-slate-400">Loading...</div>
        ) : domains.length === 0 ? (
          <div className="text-xs text-slate-400 py-4 text-center bg-slate-50 rounded-lg border border-dashed border-slate-200">
            No custom domains configured
          </div>
        ) : (
          <div className="space-y-2">
            {domains.map((domain) => (
              <div 
                key={domain} 
                className="flex items-center justify-between bg-white border border-slate-200 rounded-lg px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  <Globe size={14} className="text-emerald-500" />
                  <span className="text-sm font-medium text-slate-700">{domain}</span>
                  <a 
                    href={`https://${domain}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:text-blue-700"
                  >
                    <ExternalLink size={12} />
                  </a>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 text-red-400 hover:text-red-600 hover:bg-red-50"
                  onClick={() => removeDomain(domain)}
                >
                  <Trash2 size={14} />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Domain */}
      <div className="flex gap-2">
        <Input
          value={newDomain}
          onChange={(e) => setNewDomain(e.target.value)}
          placeholder="billing.yourcompany.com"
          className="flex-1"
          onKeyDown={(e) => e.key === "Enter" && addDomain()}
        />
        <Button onClick={addDomain} disabled={adding} size="sm">
          <Plus size={14} className="mr-1" />
          {adding ? "Adding..." : "Add"}
        </Button>
      </div>

      {/* Setup Steps */}
      <div className="border-t border-slate-100 pt-4">
        <p className="text-xs font-medium text-slate-700 mb-2">Setup Steps</p>
        <ol className="text-xs text-slate-600 space-y-1.5 list-decimal list-inside">
          <li>Add your domain above</li>
          <li>Configure DNS: Add a CNAME record pointing to <code className="bg-slate-100 px-1 rounded">{platformUrl}</code></li>
          <li>Wait for DNS propagation (5-30 minutes)</li>
          <li>SSL certificates are provisioned automatically</li>
          <li>Share your custom URL with customers - no partner code required!</li>
        </ol>
      </div>
    </div>
  );
}
