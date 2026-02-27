import { useEffect, useState, useRef, useCallback } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { toast } from "@/components/ui/sonner";
import api from "@/lib/api";
import {
  FileText, Trash2, Download, Upload, StickyNote, Search,
  RefreshCw, AlertTriangle, FolderSync, ChevronDown,
  Clock, FileSearch, ChevronsUpDown, Check
} from "lucide-react";

interface Document {
  id: string;
  file_name: string;
  customer_id: string;
  customer_name?: string;
  file_size: number;
  mime_type: string;
  uploaded_by: string;
  uploaded_by_id: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

interface Customer { id: string; email: string; name: string; }
interface Log { action: string; actor: string; created_at: string; details: Record<string, any>; }

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function AdminDocumentsTab() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [custLoading, setCustLoading] = useState(false);
  const [custOpen, setCustOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [workdriveConnected, setWorkdriveConnected] = useState<boolean | null>(null);
  const [search, setSearch] = useState("");

  // Upload modal
  const [showUpload, setShowUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadCustomerId, setUploadCustomerId] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Notes modal
  const [notesDoc, setNotesDoc] = useState<Document | null>(null);
  const [notesText, setNotesText] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);

  // Logs modal
  const [logsDoc, setLogsDoc] = useState<Document | null>(null);
  const [logs, setLogs] = useState<Log[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  // Delete confirm
  const [deleteDoc, setDeleteDoc] = useState<Document | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Sync
  const [syncing, setSyncing] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [docsRes, connRes] = await Promise.all([
        api.get("/documents"),
        api.get("/oauth/integrations"),
      ]);
      setDocs(docsRes.data.documents || []);
      const wd = (connRes.data.integrations || []).find((i: any) => i.id === "zoho_workdrive");
      setWorkdriveConnected(wd?.is_validated === true);
      // Load customer list for upload modal
      const custRes = await api.get("/admin/customers?per_page=500");
      const userMap: Record<string, any> = {};
      (custRes.data.users || []).forEach((u: any) => { userMap[u.id] = u; });
      const custs = (custRes.data.customers || []).map((c: any) => {
        const user = userMap[c.user_id] || {};
        return {
          id: c.id,
          name: user.full_name || user.email || c.company_name || c.id,
        };
      });
      setCustomers(custs);
    } catch {
      toast.error("Failed to load documents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const filtered = docs.filter(d =>
    d.file_name.toLowerCase().includes(search.toLowerCase()) ||
    (d.customer_name || "").toLowerCase().includes(search.toLowerCase()) ||
    d.customer_id.toLowerCase().includes(search.toLowerCase())
  );

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
    if (!uploadFile || !uploadCustomerId) return;
    if (uploadFile.size > 5 * 1024 * 1024) { toast.error("File exceeds 5 MB limit"); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", uploadFile);
      await api.post(`/documents/upload?customer_id=${uploadCustomerId}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Document uploaded");
      setShowUpload(false);
      setUploadFile(null);
      setUploadCustomerId("");
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Upload failed"); }
    finally { setUploading(false); }
  };

  const handleSaveNotes = async () => {
    if (!notesDoc) return;
    setSavingNotes(true);
    try {
      await api.put(`/admin/documents/${notesDoc.id}`, { notes: notesText });
      toast.success("Notes saved");
      setNotesDoc(null);
      load();
    } catch { toast.error("Failed to save notes"); }
    finally { setSavingNotes(false); }
  };

  const handleDelete = async () => {
    if (!deleteDoc) return;
    setDeleting(true);
    try {
      await api.delete(`/admin/documents/${deleteDoc.id}`);
      toast.success("Document deleted");
      setDeleteDoc(null);
      load();
    } catch { toast.error("Failed to delete document"); }
    finally { setDeleting(false); }
  };

  const openLogs = async (doc: Document) => {
    setLogsDoc(doc);
    setLogsLoading(true);
    try {
      const res = await api.get(`/admin/documents/${doc.id}/logs`);
      setLogs(res.data.logs || []);
    } catch { setLogs([]); }
    finally { setLogsLoading(false); }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await api.post("/admin/workdrive/sync-folders");
      toast.success(`Sync complete — ${res.data.created} folders created, ${res.data.skipped} skipped`);
      if (res.data.errors?.length) toast.error(`${res.data.errors.length} errors during sync`);
    } catch (e: any) { toast.error(e.response?.data?.detail || "Sync failed"); }
    finally { setSyncing(false); }
  };

  if (workdriveConnected === false) {
    return (
      <div className="py-20 flex flex-col items-center gap-4 text-center" data-testid="documents-no-workdrive">
        <div className="w-16 h-16 rounded-2xl bg-sky-50 flex items-center justify-center">
          <FileSearch size={28} className="text-sky-500" />
        </div>
        <h3 className="text-base font-semibold text-slate-800">Connect a Cloud Storage Provider</h3>
        <p className="text-sm text-slate-500 max-w-sm">
          To enable document sharing with clients, connect a cloud storage service under <strong>Connected Services</strong>.
        </p>
        <div className="flex flex-col gap-2 mt-2">
          <div className="flex items-center gap-2 text-sm text-slate-700 bg-white border border-slate-200 px-4 py-2 rounded-lg">
            <span className="w-2 h-2 rounded-full bg-sky-400" />
            Zoho WorkDrive — <span className="text-sky-600 font-medium">available</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-slate-400 bg-slate-50 border border-slate-100 px-4 py-2 rounded-lg">
            <span className="w-2 h-2 rounded-full bg-slate-300" />
            Google Drive — <span className="italic">coming soon</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-slate-400 bg-slate-50 border border-slate-100 px-4 py-2 rounded-lg">
            <span className="w-2 h-2 rounded-full bg-slate-300" />
            OneDrive — <span className="italic">coming soon</span>
          </div>
        </div>
        <Button variant="outline" size="sm" className="mt-2" onClick={() => window.location.hash = "integrations"} data-testid="go-to-integrations-btn">
          Go to Connected Services
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="admin-documents-tab">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="Search by file name or customer…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="h-8 pl-7 text-xs w-64"
            data-testid="documents-search"
          />
        </div>
        <div className="flex gap-2">
          <Button
            size="sm" variant="outline"
            onClick={handleSync} disabled={syncing || !workdriveConnected}
            className="h-8 text-xs"
            data-testid="sync-folders-btn"
          >
            {syncing ? <RefreshCw size={12} className="mr-1.5 animate-spin" /> : <FolderSync size={12} className="mr-1.5" />}
            {syncing ? "Syncing…" : "Sync Folders"}
          </Button>
          <Button
            size="sm" onClick={() => setShowUpload(true)} disabled={!workdriveConnected}
            className="h-8 text-xs"
            data-testid="upload-document-btn"
          >
            <Upload size={12} className="mr-1.5" />Upload Document
          </Button>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="py-16 text-center text-sm text-slate-400">Loading documents…</div>
      ) : filtered.length === 0 ? (
        <div className="py-16 text-center text-sm text-slate-400" data-testid="documents-empty">
          {search ? "No documents match your search." : "No documents uploaded yet. Upload the first one!"}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
          <Table data-testid="admin-documents-table">
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-xs">File Name</TableHead>
                <TableHead className="text-xs">Customer</TableHead>
                <TableHead className="text-xs">Customer ID</TableHead>
                <TableHead className="text-xs">Size</TableHead>
                <TableHead className="text-xs">Uploaded By</TableHead>
                <TableHead className="text-xs">Created</TableHead>
                <TableHead className="text-xs">Modified</TableHead>
                <TableHead className="text-xs">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map(doc => (
                <TableRow key={doc.id} className="hover:bg-slate-50/50" data-testid={`document-row-${doc.id}`}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <FileText size={14} className="text-slate-400 flex-shrink-0" />
                      <span className="text-xs font-medium text-slate-800 max-w-[180px] truncate" title={doc.file_name} data-testid={`doc-name-${doc.id}`}>
                        {doc.file_name}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-xs" data-testid={`doc-customer-name-${doc.id}`}>{doc.customer_name || "—"}</TableCell>
                  <TableCell className="font-mono text-xs text-slate-400" data-testid={`doc-customer-id-${doc.id}`}>{doc.customer_id?.slice(0, 10)}…</TableCell>
                  <TableCell className="text-xs text-slate-500" data-testid={`doc-size-${doc.id}`}>{formatSize(doc.file_size || 0)}</TableCell>
                  <TableCell className="text-xs" data-testid={`doc-uploader-${doc.id}`}>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${doc.uploaded_by === "admin" ? "bg-slate-100 text-slate-700" : "bg-sky-50 text-sky-700"}`}>
                      {doc.uploaded_by === "admin" ? "Admin" : "Customer"}
                    </span>
                  </TableCell>
                  <TableCell className="text-xs text-slate-400" data-testid={`doc-created-${doc.id}`}>{doc.created_at?.slice(0, 16).replace("T", " ") || "—"}</TableCell>
                  <TableCell className="text-xs text-slate-400" data-testid={`doc-updated-${doc.id}`}>{doc.updated_at?.slice(0, 16).replace("T", " ") || "—"}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleDownload(doc)} title="Download" data-testid={`doc-download-${doc.id}`}>
                        <Download size={13} />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => { setNotesDoc(doc); setNotesText(doc.notes || ""); }} title="Notes" data-testid={`doc-notes-${doc.id}`}>
                        <StickyNote size={13} />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openLogs(doc)} title="Logs" data-testid={`doc-logs-${doc.id}`}>
                        <Clock size={13} />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-red-400 hover:text-red-600 hover:bg-red-50" onClick={() => setDeleteDoc(doc)} title="Delete" data-testid={`doc-delete-${doc.id}`}>
                        <Trash2 size={13} />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Upload Modal */}
      <Dialog open={showUpload} onOpenChange={setShowUpload}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Upload Document</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-600 mb-1 block">Customer *</label>
              <Select value={uploadCustomerId} onValueChange={setUploadCustomerId}>
                <SelectTrigger data-testid="upload-customer-select"><SelectValue placeholder="Select customer…" /></SelectTrigger>
                <SelectContent>
                  {customers.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs text-slate-600 mb-1 block">File * (max 5 MB)</label>
              <input
                ref={fileRef} type="file"
                onChange={e => setUploadFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-slate-700 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border file:border-slate-200 file:text-xs file:bg-white hover:file:bg-slate-50"
                data-testid="upload-file-input"
              />
              {uploadFile && <p className="text-xs text-slate-400 mt-1">{uploadFile.name} ({formatSize(uploadFile.size)})</p>}
            </div>
            <Button
              className="w-full" size="sm"
              disabled={!uploadFile || !uploadCustomerId || uploading}
              onClick={handleUpload}
              data-testid="upload-submit-btn"
            >
              {uploading ? "Uploading…" : "Upload"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Notes Modal */}
      <Dialog open={!!notesDoc} onOpenChange={() => setNotesDoc(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Notes — {notesDoc?.file_name}</DialogTitle></DialogHeader>
          <textarea
            className="w-full border rounded-lg p-2 text-sm min-h-[100px] resize-none"
            placeholder="Add notes about this document…"
            value={notesText}
            onChange={e => setNotesText(e.target.value)}
            data-testid="notes-textarea"
          />
          <Button size="sm" onClick={handleSaveNotes} disabled={savingNotes} data-testid="save-notes-btn">
            {savingNotes ? "Saving…" : "Save Notes"}
          </Button>
        </DialogContent>
      </Dialog>

      {/* Logs Modal */}
      <Dialog open={!!logsDoc} onOpenChange={() => setLogsDoc(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Audit Log — {logsDoc?.file_name}</DialogTitle></DialogHeader>
          {logsLoading ? <p className="text-sm text-slate-400 py-6 text-center">Loading…</p> : logs.length === 0 ? (
            <p className="text-sm text-slate-400 py-6 text-center">No log entries found.</p>
          ) : (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {logs.map((log, i) => (
                <div key={i} className="text-xs border rounded-lg p-2 bg-slate-50">
                  <span className="font-medium">{log.action}</span> by <span className="text-slate-600">{log.actor}</span>
                  <span className="text-slate-400 ml-2">{log.created_at?.slice(0, 16).replace("T", " ")}</span>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Confirm */}
      <Dialog open={!!deleteDoc} onOpenChange={() => setDeleteDoc(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><AlertTriangle size={16} className="text-red-500" />Delete Document</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-600">
            Permanently delete <strong>{deleteDoc?.file_name}</strong>? This removes the file from WorkDrive and cannot be undone.
          </p>
          <div className="flex gap-2 justify-end">
            <Button variant="outline" size="sm" onClick={() => setDeleteDoc(null)}>Cancel</Button>
            <Button variant="destructive" size="sm" onClick={handleDelete} disabled={deleting} data-testid="confirm-delete-btn">
              {deleting ? "Deleting…" : "Delete"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
