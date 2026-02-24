import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Globe, Plus, Trash2, Info, ExternalLink, CheckCircle, AlertCircle, Clock, RefreshCw, Copy, XCircle } from "lucide-react";

interface DomainData {
  domain: string;
  status: "pending" | "verified" | "failed" | "incorrect";
  verified_at: string | null;
  added_at: string;
  last_check_at: string | null;
  last_check_message: string | null;
}

const statusConfig = {
  verified: { icon: CheckCircle, color: "text-emerald-500", bg: "bg-emerald-50", border: "border-emerald-200", label: "Verified" },
  pending: { icon: Clock, color: "text-amber-500", bg: "bg-amber-50", border: "border-amber-200", label: "Pending" },
  failed: { icon: XCircle, color: "text-red-500", bg: "bg-red-50", border: "border-red-200", label: "Failed" },
  incorrect: { icon: AlertCircle, color: "text-orange-500", bg: "bg-orange-50", border: "border-orange-200", label: "Incorrect" },
};

export function CustomDomainsSection() {
  const [domains, setDomains] = useState<DomainData[]>([]);
  const [newDomain, setNewDomain] = useState("");
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [verifying, setVerifying] = useState<string | null>(null);

  useEffect(() => {
    loadDomains();
  }, []);

  const loadDomains = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/custom-domains");
      // Handle both old format (string[]) and new format (DomainData[])
      const data = res.data.domains || [];
      if (data.length > 0 && typeof data[0] === "string") {
        // Convert legacy format
        setDomains(data.map((d: string) => ({
          domain: d,
          status: "pending",
          verified_at: null,
          added_at: new Date().toISOString(),
          last_check_at: null,
          last_check_message: null
        })));
      } else {
        setDomains(data);
      }
    } catch {
      setDomains([]);
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
      const res = await api.post("/admin/custom-domains", {
        domain: newDomain.trim().toLowerCase()
      });
      setDomains([...domains, res.data.domain]);
      setNewDomain("");
      toast.success("Domain added. Please configure DNS and verify.");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to add domain");
    } finally {
      setAdding(false);
    }
  };

  const verifyDomain = async (domain: string) => {
    setVerifying(domain);
    try {
      const res = await api.post(`/admin/custom-domains/${encodeURIComponent(domain)}/verify`);
      const verification = res.data.verification;
      
      // Update local state
      setDomains(domains.map(d => 
        d.domain === domain 
          ? { 
              ...d, 
              status: verification.status, 
              last_check_at: new Date().toISOString(),
              last_check_message: verification.message,
              verified_at: verification.verified ? new Date().toISOString() : d.verified_at
            }
          : d
      ));
      
      if (verification.verified) {
        toast.success(`Domain ${domain} verified successfully!`);
      } else {
        toast.warning(verification.message);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Verification failed");
    } finally {
      setVerifying(null);
    }
  };

  const removeDomain = async (domain: string) => {
    if (!confirm(`Remove ${domain}?`)) return;
    
    try {
      await api.delete(`/admin/custom-domains/${encodeURIComponent(domain)}`);
      setDomains(domains.filter(d => d.domain !== domain));
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
  const cnameTarget = "preview.emergentagent.com";

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
            CNAME → <span className="font-semibold">{cnameTarget}</span>
          </code>
          <Button 
            variant="ghost" 
            size="sm" 
            className="h-6 w-6 p-0"
            onClick={() => copyToClipboard(cnameTarget)}
          >
            <Copy size={12} />
          </Button>
        </div>
        <p className="text-[10px] text-slate-400 mt-2">
          Add this CNAME record in your DNS provider for each custom domain, then click "Verify" to activate
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
            {domains.map((domainData) => {
              const config = statusConfig[domainData.status] || statusConfig.pending;
              const StatusIcon = config.icon;
              
              return (
                <div 
                  key={domainData.domain} 
                  className={`border rounded-lg px-3 py-2 ${config.bg} ${config.border}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Globe size={14} className={domainData.status === "verified" ? "text-emerald-500" : "text-slate-400"} />
                      <span className="text-sm font-medium text-slate-700">{domainData.domain}</span>
                      {domainData.status === "verified" && (
                        <a 
                          href={`https://${domainData.domain}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-500 hover:text-blue-700"
                        >
                          <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-2">
                      {/* Status Badge */}
                      <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${config.color} bg-white border ${config.border}`}>
                        <StatusIcon size={10} />
                        {config.label}
                      </div>
                      
                      {/* Verify Button */}
                      {domainData.status !== "verified" && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          onClick={() => verifyDomain(domainData.domain)}
                          disabled={verifying === domainData.domain}
                        >
                          <RefreshCw size={12} className={`mr-1 ${verifying === domainData.domain ? "animate-spin" : ""}`} />
                          {verifying === domainData.domain ? "Checking..." : "Verify"}
                        </Button>
                      )}
                      
                      {/* Remove Button */}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-red-400 hover:text-red-600 hover:bg-red-50"
                        onClick={() => removeDomain(domainData.domain)}
                      >
                        <Trash2 size={14} />
                      </Button>
                    </div>
                  </div>
                  
                  {/* Status Message */}
                  {domainData.last_check_message && domainData.status !== "verified" && (
                    <div className="mt-2 text-[10px] text-slate-500 pl-6">
                      {domainData.last_check_message}
                    </div>
                  )}
                  
                  {/* Verified timestamp */}
                  {domainData.status === "verified" && domainData.verified_at && (
                    <div className="mt-1 text-[10px] text-emerald-600 pl-6">
                      Verified on {new Date(domainData.verified_at).toLocaleDateString()}
                    </div>
                  )}
                </div>
              );
            })}
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
          data-testid="add-custom-domain-input"
        />
        <Button onClick={addDomain} disabled={adding} size="sm" data-testid="add-custom-domain-btn">
          <Plus size={14} className="mr-1" />
          {adding ? "Adding..." : "Add Domain"}
        </Button>
      </div>

      {/* Setup Steps */}
      <div className="border-t border-slate-100 pt-4">
        <p className="text-xs font-medium text-slate-700 mb-2">Setup Steps</p>
        <ol className="text-xs text-slate-600 space-y-1.5 list-decimal list-inside">
          <li>Add your domain above</li>
          <li>Configure DNS: Add a CNAME record pointing to <code className="bg-slate-100 px-1 rounded">{cnameTarget}</code></li>
          <li>Wait for DNS propagation (5-30 minutes)</li>
          <li>Click "Verify" to confirm DNS configuration</li>
          <li>Once verified, SSL certificates are provisioned automatically</li>
          <li>Share your custom URL with customers - no partner code required!</li>
        </ol>
      </div>
    </div>
  );
}
