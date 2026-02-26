import { useCallback, useEffect, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { useAuth } from "@/contexts/AuthContext";
import { Mail, Clock, Trash2, Plus, ExternalLink, Download, FileText, LayoutTemplate, X, ChevronDown, Tag, Upload, ShieldCheck } from "lucide-react";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { ArticleTemplatesTab } from "./ResourceTemplatesTab";
import { ArticleEmailTemplatesTab } from "./ResourceEmailTemplatesTab";
import { ArticleCategoriesTab } from "./ResourceCategoriesTab";
import { RichHtmlEditor } from "@/components/ui/RichHtmlEditor";

const HARDCODED_CATEGORIES = [
  "Scope - Draft",
  "Scope - Final Lost",
  "Scope - Final Won",
  "Blog",
  "Help",
  "Guide",
  "SOP",
  "Other",
];

const SCOPE_FINAL = new Set(["Scope - Final Lost", "Scope - Final Won"]);

function slugify(text: string) {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function ArticleEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <RichHtmlEditor
      value={value}
      onChange={onChange}
      withImages
      minHeight="300px"
      placeholder="Write your resource content here…"
    />
  );
}

function EmailBodyComposer({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <RichHtmlEditor
      value={value}
      onChange={onChange}
      minHeight="200px"
      placeholder="Write the email body…"
    />
  );
}

interface ResourcesTabProps {
  editResourceId?: string;
}

export function ResourcesTab({ editResourceId }: ResourcesTabProps) {
  const { user: authUser } = useAuth();
  const isPlatformAdmin = authUser?.role === "platform_admin";
  const [showImportResources, setShowImportResources] = useState(false);
  const [subTab, setSubTab] = useState<"resources" | "templates" | "email-templates" | "categories">("resources");
  const [dynamicCategories, setDynamicCategories] = useState<any[]>([]);

  const loadCategories = useCallback(async () => {
    try {
      const res = await api.get("/resource-categories");
      setDynamicCategories(res.data.categories || []);
    } catch {
      // silently fall back to empty (hardcoded categories shown in select)
    }
  }, []);

  useEffect(() => { loadCategories(); }, [loadCategories]);
  const [customers, setCustomers] = useState<any[]>([]);
  // Fetch customers for visibility/email controls
  useEffect(() => {
    api.get("/admin/customers?per_page=1000")
      .then(r => { const custs = r.data.customers || []; const usrs = r.data.users || []; const um: Record<string,any> = {}; usrs.forEach((u:any) => { um[u.id] = u; }); setCustomers(custs.map((c:any) => ({ ...c, email: um[c.user_id]?.email || '', full_name: um[c.user_id]?.full_name || '' }))); })
      .catch(() => {});
  }, []);

  // Template picker state
  const [showTemplatePicker, setShowTemplatePicker] = useState(false);
  const [availableTemplates, setAvailableTemplates] = useState<any[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [editorKey, setEditorKey] = useState(0);

  const loadTemplates = async () => {
    setLoadingTemplates(true);
    try {
      const res = await api.get("/resource-templates");
      setAvailableTemplates(res.data.templates || []);
    } catch { toast.error("Failed to load templates"); }
    finally { setLoadingTemplates(false); }
  };

  // Customer search for visibility typeahead
  const [custVisSearch, setCustVisSearch] = useState("");
  const [resources, setResources] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingResource, setEditingResource] = useState<any>(null);
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const [showEmailDialog, setShowEmailDialog] = useState(false);
  const [emailTarget, setEmailTarget] = useState<any>(null);
  const [emailForm, setEmailForm] = useState({
    to: [] as string[],
    cc: [] as string[],
    bcc: [] as string[],
    subject: "",
    html_body: "",
    attach_pdf: false,
  });
  const [emailToInput, setEmailToInput] = useState("");
  const [emailCcInput, setEmailCcInput] = useState("");
  const [emailBccInput, setEmailBccInput] = useState("");
  const [showCcBcc, setShowCcBcc] = useState(false);
  const [emailEditorKey, setEmailEditorKey] = useState(0);
  const [emailTemplates, setEmailTemplates] = useState<any[]>([]);
  const [showEmailTemplatePicker, setShowEmailTemplatePicker] = useState(false);
  const [savingEmail, setSavingEmail] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [searchFilter, setSearchFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const PER_PAGE = 20;

  const [form, setForm] = useState({
    title: "",
    slug: "",
    category: "",
    price: "",
    content: "",
    visibility: "all",
    restricted_to: [] as string[],
  });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(PER_PAGE) });
      if (categoryFilter !== "all") params.append("category", categoryFilter);
      if (searchFilter) params.append("search", searchFilter);
      if (startDate) params.append("created_from", startDate);
      if (endDate) params.append("created_to", endDate);
      const res = await api.get(`/resources/admin/list?${params}`);
      setResources(res.data.resources || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
      setPage(p);
    } catch {
      toast.error("Failed to load resources");
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, searchFilter, startDate, endDate]);

  useEffect(() => { load(1); }, [categoryFilter, searchFilter, startDate, endDate]);

  // Auto-open edit dialog when navigated from resource preview with editResourceId
  useEffect(() => {
    if (editResourceId) {
      openEdit({ id: editResourceId });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editResourceId]);

  const resetForm = () => setForm({ title: "", slug: "", category: "", price: "", content: "", visibility: "all", restricted_to: [] });

  const openCreate = () => {
    resetForm();
    setEditingResource(null);
    setShowForm(true);
  };

  const openEdit = async (resource: any) => {
    setEditingResource(resource);
    try {
      const res = await api.get(`/resources/${resource.id}`);
      const a = res.data.resource;
      setEditingResource(a);
      setForm({
        title: a.title || "",
        slug: a.slug || "",
        category: a.category || "",
        price: a.price ? String(a.price) : "",
        content: a.content || "",
        visibility: a.visibility || "all",
        restricted_to: a.restricted_to || [],
      });
    } catch {
      toast.error("Failed to load resource");
      return;
    }
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.title || !form.category) {
      toast.error("Title and category are required");
      return;
    }
    if (SCOPE_FINAL.has(form.category) && !form.price) {
      toast.error("Price is required for Scope - Final resources");
      return;
    }
    setSaving(true);
    try {
      const payload: any = {
        title: form.title,
        slug: form.slug || slugify(form.title),
        category: form.category,
        price: form.price ? parseFloat(form.price) : null,
        content: form.content,
        visibility: form.visibility,
        restricted_to: form.restricted_to,
      };
      if (editingResource) {
        await api.put(`/resources/${editingResource.id}`, payload);
        toast.success("Resource updated");
      } else {
        await api.post("/resources", payload);
        toast.success("Resource created");
      }
      setShowForm(false);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save resource");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this resource? This cannot be undone.")) return;
    setDeleting(id);
    try {
      await api.delete(`/resources/${id}`);
      toast.success("Resource deleted");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Delete failed");
    } finally {
      setDeleting(null);
    }
  };

  const handleViewLogs = (resource: any) => {
    setLogsUrl(`/resources/${resource.id}/logs`);
    setShowAuditLogs(true);
  };

  const handleEmailOpen = (resource: any) => {
    setEmailTarget(resource);
    setEmailForm({ to: [], cc: [], bcc: [], subject: `Resource: ${resource.title}`, html_body: "", attach_pdf: false });
    setEmailToInput("");
    setEmailCcInput("");
    setEmailBccInput("");
    setShowCcBcc(false);
    setEmailEditorKey(k => k + 1);
    setShowEmailDialog(true);
  };

  const addEmailChip = (field: "to" | "cc" | "bcc", inputVal: string, setInput: (v: string) => void) => {
    const val = inputVal.trim().toLowerCase();
    if (!val) return;
    if (emailForm[field].includes(val)) { setInput(""); return; }
    setEmailForm(prev => ({ ...prev, [field]: [...prev[field], val] }));
    setInput("");
  };

  const removeEmailChip = (field: "to" | "cc" | "bcc", email: string) => {
    setEmailForm(prev => ({ ...prev, [field]: prev[field].filter(e => e !== email) }));
  };

  const loadEmailTemplates = async () => {
    try {
      const res = await api.get("/resource-email-templates");
      setEmailTemplates(res.data.templates || []);
    } catch { toast.error("Failed to load email templates"); }
  };

  const applyEmailTemplate = (tpl: any) => {
    setEmailForm(prev => ({ ...prev, subject: tpl.subject, html_body: tpl.html_body }));
    setEmailEditorKey(k => k + 1);
    setShowEmailTemplatePicker(false);
    toast.success(`Template "${tpl.name}" applied`);
  };

  const saveEmailAsTemplate = async () => {
    const name = prompt("Save current email as template. Name:");
    if (!name) return;
    try {
      await api.post("/resource-email-templates", {
        name,
        subject: emailForm.subject,
        html_body: emailForm.html_body,
        description: `For resource: ${emailTarget?.title || ""}`,
      });
      toast.success("Email template saved");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save template");
    }
  };

  const handleSendEmail = async () => {
    if (!emailForm.to.length) {
      toast.error("Add at least one recipient in the To field");
      return;
    }
    setSavingEmail(true);
    try {
      const res = await api.post(`/resources/${emailTarget.id}/send-email`, emailForm);
      toast.success(res.data.message || "Email sent");
      setShowEmailDialog(false);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to send email");
    } finally {
      setSavingEmail(false);
    }
  };

  const downloadCsv = () => {
    const token = localStorage.getItem("aa_token");
    const base = process.env.REACT_APP_BACKEND_URL || "";
    const params = new URLSearchParams();
    if (categoryFilter !== "all") params.append("category", categoryFilter);
    if (searchFilter) params.append("search", searchFilter);
    fetch(`${base}/api/admin/export/resources?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `resources-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  const downloadResource = (articleId: string, format: "pdf" | "docx") => {
    const token = localStorage.getItem("aa_token");
    const base = process.env.REACT_APP_BACKEND_URL || "";
    fetch(`${base}/api/resources/${articleId}/download?format=${format}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(b);
        a.download = `resource-${articleId.slice(0, 8)}.${format}`;
        a.click();
      }).catch(() => toast.error("Download failed"));
  };

  const saveAsTemplate = async (resource: any) => {
    const name = prompt(`Save "${resource.title}" as template. Template name:`, resource.title);
    if (!name) return;
    try {
      const res = await api.get(`/resources/${resource.id}`);
      const a = res.data.resource;
      await api.post("/resource-templates", {
        name,
        description: `Template created from resource: ${a.title}`,
        category: a.category,
        content: a.content,
      });
      toast.success("Saved as template");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save template");
    }
  };

  const applyTemplate = (tpl: any) => {
    setForm(prev => ({ ...prev, content: tpl.content, category: prev.category || tpl.category || "" }));
    setEditorKey(k => k + 1); // Force Tiptap editor to remount with new content
    setShowTemplatePicker(false);
    toast.success(`Template "${tpl.name}" applied`);
  };

  const appUrl = (window as any).__REACT_APP_BACKEND_URL || process.env.REACT_APP_BACKEND_URL || "";
  const frontendUrl = appUrl.replace("/api", "").replace(":8001", ":3000");

  return (
    <div className="space-y-4" data-testid="admin-resources-tab">
      <AdminPageHeader title="Resources" subtitle={subTab === "resources" ? `${total} resources` : "Manage reusable templates"} actions={
        <>
          {subTab === "resources" && (
            <>
              <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="resources-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
              <Button size="sm" variant="outline" onClick={() => setShowImportResources(true)} data-testid="resources-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
              <Button size="sm" onClick={openCreate} className="gap-2" data-testid="resources-create-btn"><Plus size={14} /> New Resource</Button>
            </>
          )}
        </>
      } />

      {/* Sub-tab switcher */}
      <div className="flex gap-1 border-b border-slate-200">
        <button onClick={() => setSubTab("resources")} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${subTab === "resources" ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700"}`} data-testid="subtab-resources">Resources</button>
        <button onClick={() => setSubTab("templates")} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${subTab === "templates" ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700"}`} data-testid="subtab-templates"><LayoutTemplate size={13} /> Templates</button>
        <button onClick={() => setSubTab("email-templates")} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${subTab === "email-templates" ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700"}`} data-testid="subtab-email-templates"><Mail size={13} /> Email Templates</button>
        <button onClick={() => setSubTab("categories")} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${subTab === "categories" ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700"}`} data-testid="subtab-categories"><Tag size={13} /> Categories</button>
      </div>

      {/* Templates sub-tab */}
      {subTab === "templates" && <ArticleTemplatesTab categories={dynamicCategories} />}

      {/* Email Templates sub-tab */}
      {subTab === "email-templates" && <ArticleEmailTemplatesTab />}

      {/* Categories sub-tab */}
      {subTab === "categories" && <ArticleCategoriesTab />}

      {/* Resources sub-tab */}
      {subTab === "resources" && (<>

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Input placeholder="Search title or ID…" value={searchFilter} onChange={e => setSearchFilter(e.target.value)} className="h-8 text-xs w-44" data-testid="resources-search-filter" />
          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="h-8 text-xs w-40 bg-white" data-testid="resources-category-filter"><SelectValue placeholder="All categories" /></SelectTrigger>
            <SelectContent><SelectItem value="all">All categories</SelectItem>{(dynamicCategories.length > 0 ? dynamicCategories.map(c => c.name) : HARDCODED_CATEGORIES).map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
          </Select>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Created</span>
            <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="h-8 text-xs w-32" data-testid="resources-start-date" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="h-8 text-xs w-32" data-testid="resources-end-date" />
          </div>
          <Button size="sm" variant="outline" onClick={() => { setSearchFilter(""); setCategoryFilter("all"); setStartDate(""); setEndDate(""); }} className="h-8 text-xs" data-testid="resources-clear-filters">Clear</Button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead className="text-xs">ID</TableHead>
              <TableHead className="text-xs">Created</TableHead>
              <TableHead className="text-xs">Modified</TableHead>
              <TableHead className="text-xs">Category</TableHead>
              <TableHead className="text-xs">Price</TableHead>
              <TableHead className="text-xs">Visible to</TableHead>
              {isPlatformAdmin && <TableHead className="text-xs">Partner</TableHead>}
              <TableHead className="text-xs">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={isPlatformAdmin ? 8 : 7} className="text-center text-slate-400 py-8 text-sm">Loading…</TableCell>
              </TableRow>
            ) : resources.length === 0 ? (
              <TableRow>
                <TableCell colSpan={isPlatformAdmin ? 8 : 7} className="text-center text-slate-400 py-8 text-sm">No resources yet.</TableCell>
              </TableRow>
            ) : resources.map((a) => (
              <TableRow key={a.id} data-testid={`resource-row-${a.id}`}>
                <TableCell className="font-mono text-xs text-slate-500">{a.id?.slice(0, 8)}</TableCell>
                <TableCell className="text-xs text-slate-500 whitespace-nowrap">{a.created_at?.slice(0, 10)}</TableCell>
                <TableCell className="text-xs text-slate-500 whitespace-nowrap">{a.updated_at?.slice(0, 10)}</TableCell>
                <TableCell>
                  <div className="text-sm font-medium text-slate-900">{a.title}</div>
                  {(() => {
                    const cat = dynamicCategories.find(c => c.name === a.category);
                    const dotColor = cat?.color;
                    const isScope = a.category?.startsWith("Scope - Final") || cat?.is_scope_final;
                    const isDraft = a.category === "Scope - Draft";
                    return (
                      <span className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded ${isScope ? "bg-green-100 text-green-700" : isDraft ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"}`}>
                        {dotColor && <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: dotColor }} />}
                        {a.category}
                      </span>
                    );
                  })()}
                </TableCell>
                <TableCell className="text-sm font-medium text-slate-900">
                  {a.price ? `$${a.price}` : "—"}
                </TableCell>
                <TableCell className="text-xs text-slate-600">
                  {a.visibility === "all" || !a.restricted_to?.length ? "All" : `${a.restricted_to.length} customer(s)`}
                </TableCell>
                {isPlatformAdmin && <TableCell className="text-xs text-slate-500">{a.partner_code || "—"}</TableCell>}
                <TableCell>
                  <div className="flex gap-1 flex-wrap">
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => openEdit(a)} data-testid={`resource-edit-${a.id}`}>
                      Edit
                    </Button>
                    <a href={`${frontendUrl}/resources/${a.slug || a.id}`} target="_blank" rel="noreferrer">
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" data-testid={`resource-view-${a.id}`}>
                        <ExternalLink size={10} /> View
                      </Button>
                    </a>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => downloadResource(a.id, "pdf")} data-testid={`resource-dl-pdf-${a.id}`}>
                      <FileText size={10} /> PDF
                    </Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => downloadResource(a.id, "docx")} data-testid={`resource-dl-docx-${a.id}`}>
                      <Download size={10} /> DOCX
                    </Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => saveAsTemplate(a)} data-testid={`resource-save-template-${a.id}`}>
                      <LayoutTemplate size={10} /> Template
                    </Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => handleViewLogs(a)} data-testid={`resource-logs-${a.id}`}>
                      <Clock size={10} /> Logs
                    </Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => handleEmailOpen(a)} data-testid={`resource-email-${a.id}`}>
                      <Mail size={10} /> Email
                    </Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1 text-red-500 hover:text-red-700" onClick={() => handleDelete(a.id)} disabled={deleting === a.id} data-testid={`resource-delete-${a.id}`}>
                      <Trash2 size={10} /> Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={total} perPage={PER_PAGE} onPage={(p) => load(p)} />

      {/* Create / Edit Dialog */}
      <Dialog open={showForm} onOpenChange={(o) => { setShowForm(o); if (!o) setEditingResource(null); }}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="resource-form-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between">
              <span>{editingResource ? `Edit: ${editingResource.title}` : "New Resource"}</span>
              <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={() => { loadTemplates(); setShowTemplatePicker(true); }} data-testid="resource-use-template-btn">
                <LayoutTemplate size={13} /> Use Template
              </Button>
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">Title *</label>
                <Input
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value, slug: slugify(e.target.value) })}
                  placeholder="Resource title"
                  data-testid="resource-title-input"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">Slug / URL</label>
                <Input
                  value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value })}
                  placeholder="auto-generated"
                  className="font-mono text-sm"
                  data-testid="resource-slug-input"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">Category *</label>
                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v, price: SCOPE_FINAL.has(v) ? form.price : "" })}>
                  <SelectTrigger data-testid="resource-category-select">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {/* Show dynamic categories first, then hardcoded ones if not already included */}
                    {dynamicCategories.map(c => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
                    {HARDCODED_CATEGORIES.filter(hc => !dynamicCategories.some(dc => dc.name === hc)).map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {SCOPE_FINAL.has(form.category) && (
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-700">Price * <span className="text-slate-400">(required for Scope - Final)</span></label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.price}
                    onChange={(e) => setForm({ ...form, price: e.target.value })}
                    placeholder="0.00"
                    data-testid="resource-price-input"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-700">Currency</label>
                  <select
                    value={form.currency || "USD"}
                    onChange={(e) => setForm({ ...form, currency: e.target.value })}
                    className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                    data-testid="resource-currency-input"
                  >
                    {["USD", "CAD", "EUR", "AUD", "GBP", "INR", "MXN"].map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-700">Show this resource to</label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="radio" checked={form.visibility === "all"} onChange={() => setForm({ ...form, visibility: "all", restricted_to: [] })} />
                  All customers
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="radio" checked={form.visibility === "restricted"} onChange={() => setForm({ ...form, visibility: "restricted" })} />
                  Specific customers only
                </label>
              </div>
              {form.visibility === "restricted" && (
                <div className="space-y-2">
                  <label className="text-xs text-slate-500">Search and add customers by email</label>
                  <Input
                    placeholder="Type email to search…"
                    value={custVisSearch}
                    onChange={e => setCustVisSearch(e.target.value)}
                    className="h-9"
                    data-testid="resource-customer-search"
                  />
                  {custVisSearch && (
                    <div className="border border-slate-200 rounded bg-white shadow-md max-h-40 overflow-y-auto">
                      {customers.filter(c => c.email?.toLowerCase().includes(custVisSearch.toLowerCase()) || c.company_name?.toLowerCase().includes(custVisSearch.toLowerCase())).slice(0, 10).map((c: any) => (
                        <div key={c.id} onClick={() => { if (!form.restricted_to.includes(c.id)) setForm({ ...form, restricted_to: [...form.restricted_to, c.id] }); setCustVisSearch(""); }} className={`px-3 py-2 hover:bg-slate-50 cursor-pointer text-sm ${form.restricted_to.includes(c.id) ? "text-slate-300 cursor-not-allowed" : ""}`}>
                          {c.email || c.company_name || c.id} {c.company_name && c.email ? `— ${c.company_name}` : ""}
                          {form.restricted_to.includes(c.id) && " ✓"}
                        </div>
                      ))}
                      {customers.filter(c => c.email?.toLowerCase().includes(custVisSearch.toLowerCase())).length === 0 && <div className="px-3 py-2 text-xs text-slate-400">No customers found</div>}
                    </div>
                  )}
                  {/* Selected chips */}
                  {form.restricted_to.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {form.restricted_to.map((custId: string) => {
                        const c = customers.find((x: any) => x.id === custId);
                        return (
                          <span key={custId} className="inline-flex items-center gap-1 bg-slate-100 text-slate-700 text-xs px-2 py-1 rounded-full">
                            {c?.email || custId.slice(0, 8)}
                            <button onClick={() => setForm({ ...form, restricted_to: form.restricted_to.filter((id: string) => id !== custId) })} className="text-slate-400 hover:text-red-500 font-bold">×</button>
                          </span>
                        );
                      })}
                    </div>
                  )}
                  <p className="text-xs text-slate-400">{form.restricted_to.length} customer(s) selected</p>
                </div>
              )}
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Content</label>
              <ArticleEditor key={`editor-${editorKey}`} value={form.content} onChange={(v) => setForm({ ...form, content: v })} />
            </div>

            <div className="flex gap-2 pt-2">
              <Button onClick={handleSave} disabled={saving} data-testid="resource-save-btn">
                {saving ? "Saving…" : editingResource ? "Update Resource" : "Create Resource"}
              </Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Logs Dialog */}
      <AuditLogDialog open={showAuditLogs} onOpenChange={setShowAuditLogs} title="Resource Activity Log" logsUrl={logsUrl} />

      {/* Email Dialog */}
      <Dialog open={showEmailDialog} onOpenChange={setShowEmailDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="resource-email-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between gap-2">
              <span className="truncate">Email Resource: {emailTarget?.title}</span>
              <div className="flex gap-2 shrink-0">
                <Button variant="outline" size="sm" className="text-xs gap-1" onClick={() => { loadEmailTemplates(); setShowEmailTemplatePicker(true); }} data-testid="email-load-template-btn">
                  <LayoutTemplate size={12} /> Load Template
                </Button>
                <Button variant="outline" size="sm" className="text-xs gap-1" onClick={saveEmailAsTemplate} data-testid="email-save-template-btn">
                  <FileText size={12} /> Save Template
                </Button>
              </div>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-3 py-1">
            {/* To field */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-slate-700">To *</label>
                <button type="button" onClick={() => setShowCcBcc(v => !v)} className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-0.5">
                  CC / BCC <ChevronDown size={12} className={`transition-transform ${showCcBcc ? "rotate-180" : ""}`} />
                </button>
              </div>
              <div className="flex flex-wrap gap-1 p-2 border border-slate-200 rounded-md min-h-[38px] bg-white focus-within:ring-1 focus-within:ring-slate-300">
                {emailForm.to.map(e => (
                  <span key={e} className="inline-flex items-center gap-1 bg-slate-800 text-white text-xs px-2 py-0.5 rounded-full">
                    {e}
                    <button onClick={() => removeEmailChip("to", e)} className="hover:text-red-300"><X size={10} /></button>
                  </span>
                ))}
                <input
                  value={emailToInput}
                  onChange={e => setEmailToInput(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addEmailChip("to", emailToInput, setEmailToInput); } }}
                  onBlur={() => addEmailChip("to", emailToInput, setEmailToInput)}
                  placeholder={emailForm.to.length === 0 ? "Type email and press Enter…" : ""}
                  className="flex-1 min-w-[180px] outline-none text-sm bg-transparent"
                  data-testid="email-to-input"
                />
              </div>
              <p className="text-[11px] text-slate-400">{emailForm.to.length} recipient{emailForm.to.length !== 1 ? "s" : ""}</p>
            </div>

            {/* CC / BCC */}
            {showCcBcc && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-700">CC</label>
                  <div className="flex flex-wrap gap-1 p-2 border border-slate-200 rounded-md min-h-[38px] bg-white focus-within:ring-1 focus-within:ring-slate-300">
                    {emailForm.cc.map(e => (
                      <span key={e} className="inline-flex items-center gap-1 bg-slate-200 text-slate-700 text-xs px-2 py-0.5 rounded-full">
                        {e} <button onClick={() => removeEmailChip("cc", e)} className="hover:text-red-500"><X size={10} /></button>
                      </span>
                    ))}
                    <input
                      value={emailCcInput}
                      onChange={e => setEmailCcInput(e.target.value)}
                      onKeyDown={e => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addEmailChip("cc", emailCcInput, setEmailCcInput); } }}
                      onBlur={() => addEmailChip("cc", emailCcInput, setEmailCcInput)}
                      placeholder="Type email…"
                      className="flex-1 min-w-[120px] outline-none text-sm bg-transparent"
                      data-testid="email-cc-input"
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-700">BCC</label>
                  <div className="flex flex-wrap gap-1 p-2 border border-slate-200 rounded-md min-h-[38px] bg-white focus-within:ring-1 focus-within:ring-slate-300">
                    {emailForm.bcc.map(e => (
                      <span key={e} className="inline-flex items-center gap-1 bg-slate-200 text-slate-700 text-xs px-2 py-0.5 rounded-full">
                        {e} <button onClick={() => removeEmailChip("bcc", e)} className="hover:text-red-500"><X size={10} /></button>
                      </span>
                    ))}
                    <input
                      value={emailBccInput}
                      onChange={e => setEmailBccInput(e.target.value)}
                      onKeyDown={e => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addEmailChip("bcc", emailBccInput, setEmailBccInput); } }}
                      onBlur={() => addEmailChip("bcc", emailBccInput, setEmailBccInput)}
                      placeholder="Type email…"
                      className="flex-1 min-w-[120px] outline-none text-sm bg-transparent"
                      data-testid="email-bcc-input"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Subject */}
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Subject</label>
              <Input
                value={emailForm.subject}
                onChange={(e) => setEmailForm({ ...emailForm, subject: e.target.value })}
                data-testid="email-subject-input"
              />
            </div>

            {/* Rich text body */}
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Message Body</label>
              <EmailBodyComposer
                key={`email-body-${emailEditorKey}`}
                value={emailForm.html_body}
                onChange={(v) => setEmailForm(prev => ({ ...prev, html_body: v }))}
              />
            </div>

            {/* Attach PDF */}
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={emailForm.attach_pdf}
                onChange={(e) => setEmailForm(prev => ({ ...prev, attach_pdf: e.target.checked }))}
                className="rounded border-slate-300"
                data-testid="email-attach-pdf-checkbox"
              />
              <span className="text-sm text-slate-700">Attach resource as PDF</span>
              <span className="text-xs text-slate-400">(branded with store settings)</span>
            </label>

            <div className="flex gap-2 pt-1">
              <Button className="flex-1" onClick={handleSendEmail} disabled={savingEmail} data-testid="email-send-btn">
                {savingEmail ? "Sending…" : `Send to ${emailForm.to.length || 0} recipient${emailForm.to.length !== 1 ? "s" : ""}`}
              </Button>
              <Button variant="outline" onClick={() => setShowEmailDialog(false)}>Cancel</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Email Template Picker */}
      <Dialog open={showEmailTemplatePicker} onOpenChange={setShowEmailTemplatePicker}>
        <DialogContent className="max-w-xl max-h-[70vh] overflow-y-auto" data-testid="email-template-picker-dialog">
          <DialogHeader><DialogTitle>Choose Email Template</DialogTitle></DialogHeader>
          <p className="text-xs text-slate-500 -mt-1 mb-3">Select a template to pre-fill the subject and body.</p>
          {emailTemplates.length === 0 ? (
            <div className="text-center text-slate-400 py-8 text-sm">No email templates yet. Create some in the Email Templates tab.</div>
          ) : (
            <div className="grid gap-2">
              {emailTemplates.map((tpl) => (
                <button key={tpl.id} onClick={() => applyEmailTemplate(tpl)}
                  className="text-left border border-slate-200 rounded-lg p-3 hover:border-slate-900 hover:bg-slate-50 transition-all group"
                  data-testid={`pick-email-template-${tpl.id}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{tpl.name}</div>
                      <div className="text-xs text-slate-500 mt-0.5">{tpl.subject}</div>
                      {tpl.description && <div className="text-xs text-slate-400 mt-0.5">{tpl.description}</div>}
                    </div>
                    <span className="text-xs text-slate-900 font-medium opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Use →</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Template Picker Dialog */}
      <Dialog open={showTemplatePicker} onOpenChange={setShowTemplatePicker}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto" data-testid="template-picker-dialog">
          <DialogHeader><DialogTitle>Choose a Template</DialogTitle></DialogHeader>
          <p className="text-xs text-slate-500 -mt-1 mb-3">Select a template to pre-fill the resource content. Your title and category will be preserved.</p>
          {loadingTemplates ? (
            <div className="text-center text-slate-400 py-8 text-sm">Loading templates…</div>
          ) : availableTemplates.length === 0 ? (
            <div className="text-center text-slate-400 py-8 text-sm">No templates available. Create some in the Templates tab.</div>
          ) : (
            <div className="grid grid-cols-1 gap-2">
              {availableTemplates.map((tpl) => (
                <button key={tpl.id} onClick={() => applyTemplate(tpl)}
                  className="text-left border border-slate-200 rounded-lg p-4 hover:border-slate-900 hover:bg-slate-50 transition-all group"
                  data-testid={`pick-template-${tpl.id}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-slate-900">{tpl.name}</span>
                        {tpl.is_default && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700">Default</span>}
                        {tpl.category && <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">{tpl.category}</span>}
                      </div>
                      {tpl.description && <p className="text-xs text-slate-500 mt-1">{tpl.description}</p>}
                    </div>
                    <span className="text-xs text-slate-900 font-medium opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Use this →</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>) /* end resources sub-tab */}
      <ImportModal
        entity="resources"
        entityLabel="Resources"
        open={showImportResources}
        onClose={() => setShowImportResources(false)}
        onSuccess={() => load()}
      />
    </div>
  );
}
