import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { Plus } from "lucide-react";

export function TermsTab() {
  const [terms, setTerms] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newTerms, setNewTerms] = useState({ title: "", content: "", is_default: false, status: "active" });

  const load = async () => {
    try {
      const [termsRes, prodRes] = await Promise.all([
        api.get("/terms"),
        api.get("/products"),
      ]);
      setTerms(termsRes.data.terms || []);
      setProducts(prodRes.data.products || []);
    } catch { toast.error("Failed to load terms"); }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    try {
      await api.post("/admin/terms", newTerms);
      toast.success("Terms created");
      setShowCreateDialog(false);
      setNewTerms({ title: "", content: "", is_default: false, status: "active" });
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Failed to create terms"); }
  };

  const filtered = terms.filter(t => statusFilter === "all" || t.status === statusFilter);

  return (
    <div className="space-y-4" data-testid="terms-tab">
      <AdminPageHeader
        title="Terms & Conditions"
        subtitle={`${terms.length} documents`}
        actions={
          <Button size="sm" onClick={() => setShowCreateDialog(true)} data-testid="admin-terms-create-btn"><Plus size={14} className="mr-1" />Create Terms</Button>
        }
      />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex gap-2 items-center">
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="h-8 text-xs border border-slate-200 rounded px-2 bg-white" data-testid="admin-terms-status-filter">
            <option value="all">All Statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <Button size="sm" variant="outline" onClick={() => setStatusFilter("all")} className="h-8 text-xs">Clear</Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <Table data-testid="admin-terms-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Title</TableHead>
              <TableHead>Preview</TableHead>
              <TableHead>Products Linked</TableHead>
              <TableHead>Default</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((t: any) => {
              const linkedProducts = products.filter((p: any) => p.terms_id === t.id);
              return (
                <TableRow key={t.id} data-testid={`admin-terms-row-${t.id}`} className="border-b border-slate-100">
                  <TableCell className="font-semibold">{t.title}</TableCell>
                  <TableCell className="text-xs text-slate-500 max-w-xs truncate">{t.content}</TableCell>
                  <TableCell>
                    {linkedProducts.length === 0 ? (
                      <span className="text-xs text-slate-400">None assigned</span>
                    ) : (
                      <div className="space-y-0.5">
                        {linkedProducts.slice(0, 3).map((p: any) => (
                          <div key={p.id} className="text-xs text-slate-600">{p.name}</div>
                        ))}
                        {linkedProducts.length > 3 && <div className="text-xs text-slate-400">+{linkedProducts.length - 3} more</div>}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>{t.is_default ? <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700">Default</span> : "—"}</TableCell>
                  <TableCell>
                    <span className={`text-xs px-2 py-1 rounded ${t.status === "active" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"}`}>{t.status}</span>
                  </TableCell>
                  <TableCell className="text-xs">{new Date(t.created_at).toLocaleDateString()}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Create Terms Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-2xl" data-testid="admin-terms-dialog">
          <DialogHeader><DialogTitle>Create Terms & Conditions</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Title</label>
              <Input placeholder="Default Terms & Conditions" value={newTerms.title} onChange={e => setNewTerms({ ...newTerms, title: e.target.value })} data-testid="admin-terms-title-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Content (supports dynamic tags)</label>
              <Textarea placeholder="{company_name} {product_name} - TEST" value={newTerms.content} onChange={e => setNewTerms({ ...newTerms, content: e.target.value })} rows={8} data-testid="admin-terms-content-input" />
              <p className="text-xs text-slate-400">Available tags: {'{product_name}'}, {'{user_name}'}, {'{company_name}'}, {'{user_job_title}'}, {'{user_email}'}, {'{user_address_line1}'}, {'{user_city}'}, {'{user_state}'}, {'{user_postal}'}, {'{user_country}'}</p>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" checked={newTerms.is_default} onChange={e => setNewTerms({ ...newTerms, is_default: e.target.checked })} />
              <label className="text-sm">Set as default T&C</label>
            </div>
            <Button onClick={handleCreate} className="w-full" data-testid="admin-terms-submit">Create</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
