import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import api from "@/lib/api";
import { Upload, Download, FileText, FileSearch, Clock } from "lucide-react";

interface Document {
  id: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  uploaded_by: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function Documents() {
  const { user } = useAuth();
  const ws = useWebsite();
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      if (ws.workdrive_enabled) {
        const res = await api.get("/documents");
        setDocs(res.data.documents || []);
      }
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  useEffect(() => { if (user) load(); }, [user, ws.workdrive_enabled]);

  const handleDownload = async (doc: Document) => {
    try {
      const resp = await api.get(`/documents/${doc.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = doc.file_name;
      a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Download failed"); }
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    if (uploadFile.size > 5 * 1024 * 1024) { toast.error("File exceeds 5 MB limit"); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", uploadFile);
      await api.post("/documents/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Document uploaded successfully");
      setUploadFile(null);
      if (fileRef.current) fileRef.current.value = "";
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Upload failed"); }
    finally { setUploading(false); }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-slate-500">Please log in to view your documents.</p>
      </div>
    );
  }

  if (!ws.workdrive_enabled) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center space-y-3" data-testid="documents-unavailable">
          <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto">
            <FileSearch size={28} className="text-slate-400" />
          </div>
          <h3 className="text-base font-semibold text-slate-700">Documents Not Available</h3>
          <p className="text-sm text-slate-400 max-w-xs">
            Document sharing hasn't been set up for your account yet. Please contact your account manager.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6" data-testid="customer-documents-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">{ws.documents_page_title || "My Documents"}</h1>
          <p className="text-sm text-slate-500 mt-0.5">{ws.documents_page_subtitle || "View and upload documents shared with your account"}</p>
        </div>
      </div>

      {/* Upload section */}
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5" data-testid="upload-section">
        <p className="text-sm font-medium text-slate-700 mb-2">{ws.documents_page_upload_label || "Upload a Document"}</p>
        <p className="text-xs text-slate-400 mb-3">{ws.documents_page_upload_hint || "Supported: PDF, Word, Excel, images. Max 5 MB."}</p>
        <div className="flex items-center gap-3 flex-wrap">
          <input
            ref={fileRef}
            type="file"
            onChange={e => setUploadFile(e.target.files?.[0] || null)}
            className="block text-xs text-slate-700 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border file:border-slate-200 file:text-xs file:bg-white hover:file:bg-slate-50"
            data-testid="customer-upload-input"
          />
          {uploadFile && (
            <Button size="sm" onClick={handleUpload} disabled={uploading} data-testid="customer-upload-btn">
              <Upload size={13} className="mr-1.5" />
              {uploading ? "Uploading…" : `Upload ${uploadFile.name}`}
            </Button>
          )}
        </div>
        {uploadFile && (
          <p className="text-xs text-slate-400 mt-2">{uploadFile.name} — {formatSize(uploadFile.size)}</p>
        )}
      </div>

      {/* Documents list */}
      {docs.length === 0 ? (
        <div className="py-16 text-center" data-testid="no-documents">
          <FileText size={32} className="mx-auto text-slate-300 mb-3" />
          <p className="text-sm text-slate-400">{ws.documents_page_empty_text || "No documents yet. Upload a file or wait for your account manager to share documents with you."}</p>
        </div>
      ) : (
        <div className="space-y-2" data-testid="documents-list">
          {docs.map(doc => (
            <div key={doc.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 hover:bg-slate-50/50 transition-colors" data-testid={`customer-doc-${doc.id}`}>
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
                  <FileText size={16} className="text-slate-500" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate" data-testid={`customer-doc-name-${doc.id}`}>{doc.file_name}</p>
                  <div className="flex items-center gap-3 text-xs text-slate-400">
                    <span>{formatSize(doc.file_size || 0)}</span>
                    <span>·</span>
                    <span className={doc.uploaded_by === "admin" ? "text-sky-600" : "text-slate-400"}>
                      {doc.uploaded_by === "admin" ? "Shared by admin" : "Uploaded by you"}
                    </span>
                    <span>·</span>
                    <span><Clock size={10} className="inline mr-0.5" />{doc.created_at?.slice(0, 10) || "—"}</span>
                  </div>
                  {doc.notes && <p className="text-xs text-slate-500 mt-0.5 italic truncate">{doc.notes}</p>}
                </div>
              </div>
              <Button variant="ghost" size="sm" className="h-8 text-xs flex-shrink-0" onClick={() => handleDownload(doc)} data-testid={`customer-doc-download-${doc.id}`}>
                <Download size={13} className="mr-1.5" />Download
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
