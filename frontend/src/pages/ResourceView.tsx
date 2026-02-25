import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "@/components/AppShell";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ChevronLeft, Download, FileText, Pencil } from "lucide-react";
import { toast } from "@/components/ui/sonner";
import { useAuth } from "@/contexts/AuthContext";

export default function ResourceView() {
  const { articleId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === 'platform_admin' || user?.role === 'super_admin' || user?.role === 'partner_super_admin';
  const [resource, setResource] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const downloadResource = (format: "pdf" | "docx") => {
    const token = localStorage.getItem("aa_token");
    const base = process.env.REACT_APP_BACKEND_URL || "";
    fetch(`${base}/api/resources/${articleId}/download?format=${format}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.blob())
      .then(b => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(b);
        a.download = `${resource?.title || "resource"}.${format}`;
        a.click();
      })
      .catch(() => toast.error("Download failed"));
  };

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get(`/resources/${articleId}`);
        setResource(res.data.resource);
      } catch (e: any) {
        setError(e.response?.data?.detail || "Resource not found");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [articleId]);

  if (loading) {
    return (
      <AppShell activeCategory={null}>
        <div className="text-slate-400 text-sm py-12 text-center" data-testid="resource-loading">Loading…</div>
      </AppShell>
    );
  }

  if (error || !resource) {
    return (
      <AppShell activeCategory={null}>
        <div className="py-12 text-center space-y-4" data-testid="resource-not-found">
          <p className="text-slate-500">{error || "Resource not found"}</p>
          <Button variant="outline" onClick={() => navigate("/resources")}>
            <ChevronLeft size={14} className="mr-1" /> Back to Resources
          </Button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell activeCategory={null}>
      <div className="max-w-3xl mx-auto space-y-6" data-testid="resource-view">
        <div className="flex items-center justify-between">
          <Button variant="ghost" className="gap-1 text-slate-500 -ml-2" onClick={() => navigate("/resources")} data-testid="resource-back-btn">
            <ChevronLeft size={14} /> Back to Resources
          </Button>
          <div className="flex gap-2">
            {isAdmin && (
              <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={() => navigate(`/admin?editResource=${resource.id}`)} data-testid="resource-edit-admin-btn">
                <Pencil size={13} /> Edit Resource
              </Button>
            )}
            <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={() => downloadResource("pdf")} data-testid="resource-download-pdf">
              <FileText size={13} /> PDF
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={() => downloadResource("docx")} data-testid="resource-download-docx">
              <Download size={13} /> DOCX
            </Button>
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 font-medium border border-slate-200">
              {resource.category}
            </span>
            {resource.price && (
              <span className="text-sm font-semibold text-green-700 bg-green-50 px-2.5 py-1 rounded-full border border-green-200">
                ${resource.price}
              </span>
            )}
          </div>
          <h1 className="text-3xl font-bold text-slate-900 leading-tight" data-testid="resource-title">
            {resource.title}
          </h1>
          <p className="text-sm text-slate-400">
            Last updated {new Date(resource.updated_at).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
          </p>
          <div className="flex flex-wrap gap-4 text-xs text-slate-400 pt-1 border-t border-slate-100">
            <div className="flex items-center gap-1">
              <span className="font-medium text-slate-500">Short ID:</span>
              <code
                className="bg-slate-100 px-1.5 py-0.5 rounded font-mono cursor-pointer hover:bg-slate-200 transition-colors"
                title="Click to copy"
                onClick={() => { navigator.clipboard.writeText(resource.id.slice(0, 8)); }}
                data-testid="resource-short-id"
              >
                {resource.id.slice(0, 8)}
              </code>
            </div>
            <div className="flex items-center gap-1">
              <span className="font-medium text-slate-500">Resource ID:</span>
              <code
                className="bg-slate-100 px-1.5 py-0.5 rounded font-mono cursor-pointer hover:bg-slate-200 transition-colors"
                title="Click to copy"
                onClick={() => { navigator.clipboard.writeText(resource.id); }}
                data-testid="resource-full-id"
              >
                {resource.id}
              </code>
            </div>
          </div>
        </div>

        <div
          className="prose prose-slate max-w-none border-t border-slate-100 pt-6"
          data-testid="resource-content"
          dangerouslySetInnerHTML={{ __html: resource.content || "<p class='text-slate-400'>No content yet.</p>" }}
        />
      </div>
    </AppShell>
  );
}
