import { useState, useRef, useCallback } from "react";
import api from "@/lib/api";
import { Upload, Download, X, CheckCircle, AlertCircle, FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";

interface ImportResult {
  created: number;
  updated: number;
  errors: Array<{ row: number; error: string; data?: Record<string, string> }>;
  total: number;
  skipped?: number;
}

interface Props {
  entity: string;
  entityLabel: string;
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function ImportModal({ entity, entityLabel, open, onClose, onSuccess }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string[][] | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const parsePreview = (f: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = (e.target?.result as string) || "";
      const lines = text.split("\n").filter(Boolean).slice(0, 6); // header + 5 rows
      const rows = lines.map(line => {
        // Simple CSV split (handles quoted values)
        const result: string[] = [];
        let current = "";
        let inQuotes = false;
        for (const ch of line) {
          if (ch === '"') { inQuotes = !inQuotes; }
          else if (ch === "," && !inQuotes) { result.push(current.trim()); current = ""; }
          else { current += ch; }
        }
        result.push(current.trim());
        return result;
      });
      setPreview(rows);
    };
    reader.readAsText(f);
  };

  const handleFile = (f: File) => {
    if (!f.name.toLowerCase().endsWith(".csv")) {
      toast.error("Please upload a CSV file");
      return;
    }
    setFile(f);
    setResult(null);
    parsePreview(f);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, []);

  const handleImport = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post(`/admin/import/${entity}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(res.data);
      if (res.data.errors?.length === 0) {
        toast.success(`Import complete: ${res.data.created} created, ${res.data.updated} updated`);
        onSuccess?.();
      } else {
        toast.warning(`Import done with ${res.data.errors.length} error(s)`);
      }
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Import failed");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadTemplate = () => {
    const API_URL = process.env.REACT_APP_BACKEND_URL || "";
    const token = localStorage.getItem("aa_token") || "";
    const link = document.createElement("a");
    link.href = `${API_URL}/api/admin/import/template/${entity}`;
    // Add auth header via fetch + blob
    fetch(`${API_URL}/api/admin/import/template/${entity}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob);
        link.href = url;
        link.download = `import_template_${entity}.csv`;
        link.click();
        URL.revokeObjectURL(url);
      });
  };

  const maxPreviewCols = 8;
  const displayedCols = preview ? Math.min(preview[0]?.length || 0, maxPreviewCols) : 0;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <Upload className="h-4 w-4" />
            Import {entityLabel}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Template download */}
          <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-200">
            <div>
              <p className="text-sm font-medium text-slate-800">Download Sample Template</p>
              <p className="text-xs text-slate-500">CSV with all fields + example row. JSON fields shown as JSON strings.</p>
            </div>
            <Button variant="outline" size="sm" onClick={handleDownloadTemplate} className="gap-2">
              <Download className="h-3.5 w-3.5" />
              Template
            </Button>
          </div>

          {/* Drop zone */}
          {!result && (
            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onClick={() => inputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                dragging ? "border-slate-400 bg-slate-50" : file ? "border-green-300 bg-green-50" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
              }`}
              data-testid="import-dropzone"
            >
              <input
                ref={inputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
              />
              {file ? (
                <div className="flex items-center justify-center gap-2">
                  <FileText className="h-5 w-5 text-green-600" />
                  <span className="text-sm font-medium text-green-700">{file.name}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); reset(); }}
                    className="text-slate-400 hover:text-red-500"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <>
                  <Upload className="mx-auto h-8 w-8 text-slate-300 mb-2" />
                  <p className="text-sm text-slate-600 font-medium">Drag & drop CSV or click to browse</p>
                  <p className="text-xs text-slate-400 mt-1">CSV files only. Rows with an existing <code className="bg-slate-100 px-1 rounded">id</code> will be updated; others will be created.</p>
                </>
              )}
            </div>
          )}

          {/* Preview table */}
          {preview && !result && (
            <div>
              <p className="text-xs font-medium text-slate-600 mb-2">Preview — first {preview.length - 1} data row(s){preview[0]?.length > maxPreviewCols ? ` (showing ${maxPreviewCols} of ${preview[0]?.length} columns)` : ""}</p>
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-xs">
                  <thead className="bg-slate-50">
                    <tr>
                      {(preview[0] || []).slice(0, maxPreviewCols).map((h, i) => (
                        <th key={i} className="px-3 py-2 text-left font-semibold text-slate-700 border-b border-slate-200 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.slice(1).map((row, ri) => (
                      <tr key={ri} className="border-b border-slate-100 last:border-0">
                        {row.slice(0, maxPreviewCols).map((cell, ci) => (
                          <td key={ci} className="px-3 py-2 text-slate-600 max-w-[180px] truncate">{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Result */}
          {result && (
            <div className="space-y-3" data-testid="import-result">
              <div className={`flex items-start gap-3 p-4 rounded-lg ${result.errors.length === 0 ? "bg-green-50 border border-green-200" : "bg-amber-50 border border-amber-200"}`}>
                {result.errors.length === 0 ? (
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-amber-500 mt-0.5 shrink-0" />
                )}
                <div>
                  <p className="text-sm font-semibold">{result.errors.length === 0 ? "Import Successful" : "Import Completed with Errors"}</p>
                  <p className="text-xs text-slate-600 mt-0.5">
                    {result.created} created · {result.updated} updated · {result.errors.length} errors · {result.total} total rows
                  </p>
                </div>
              </div>
              {result.errors.length > 0 && (
                <div className="rounded-lg border border-red-200 overflow-hidden">
                  <div className="px-3 py-2 bg-red-50 text-xs font-semibold text-red-700">Errors ({result.errors.length})</div>
                  <div className="max-h-48 overflow-y-auto divide-y divide-red-100">
                    {result.errors.map((err, i) => (
                      <div key={i} className="px-3 py-2">
                        <span className="text-xs font-medium text-red-600">Row {err.row}:</span>
                        <span className="text-xs text-slate-600 ml-1">{err.error}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <Button variant="outline" size="sm" onClick={reset}>Import Another File</Button>
            </div>
          )}

          {/* Actions */}
          {file && !result && (
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button variant="outline" onClick={handleClose} disabled={loading}>Cancel</Button>
              <Button onClick={handleImport} disabled={loading} className="gap-2">
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                {loading ? "Importing…" : "Import"}
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
