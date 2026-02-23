import { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import ImageExt from "@tiptap/extension-image";
import LinkExt from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Bold, Italic, List, ListOrdered, Link2, Image, Heading1, Heading2, Heading3, Mail, Clock, Trash2, Plus, ExternalLink, Download, FileText, LayoutTemplate, X, ChevronDown } from "lucide-react";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { ArticleTemplatesTab } from "./ArticleTemplatesTab";
import { ArticleEmailTemplatesTab } from "./ArticleEmailTemplatesTab";

const ARTICLE_CATEGORIES = [
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

function RichTextToolbar({ editor }: { editor: any }) {
  const imgInputRef = useRef<HTMLInputElement>(null);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !editor) return;
    const reader = new FileReader();
    reader.onload = () => {
      const src = reader.result as string;
      editor.chain().focus().setImage({ src }).run();
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  if (!editor) return null;

  const btn = (active: boolean, onClick: () => void, children: React.ReactNode, title: string) => (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`p-1.5 rounded hover:bg-slate-100 transition-colors ${active ? "bg-slate-200 text-slate-900" : "text-slate-500"}`}
    >
      {children}
    </button>
  );

  return (
    <div className="flex flex-wrap gap-0.5 p-2 border-b border-slate-200 bg-slate-50 rounded-t-lg">
      {btn(editor.isActive("bold"), () => editor.chain().focus().toggleBold().run(), <Bold size={14} />, "Bold")}
      {btn(editor.isActive("italic"), () => editor.chain().focus().toggleItalic().run(), <Italic size={14} />, "Italic")}
      <div className="w-px bg-slate-200 mx-1" />
      {btn(editor.isActive("heading", { level: 1 }), () => editor.chain().focus().toggleHeading({ level: 1 }).run(), <Heading1 size={14} />, "H1")}
      {btn(editor.isActive("heading", { level: 2 }), () => editor.chain().focus().toggleHeading({ level: 2 }).run(), <Heading2 size={14} />, "H2")}
      {btn(editor.isActive("heading", { level: 3 }), () => editor.chain().focus().toggleHeading({ level: 3 }).run(), <Heading3 size={14} />, "H3")}
      <div className="w-px bg-slate-200 mx-1" />
      {btn(editor.isActive("bulletList"), () => editor.chain().focus().toggleBulletList().run(), <List size={14} />, "Bullet list")}
      {btn(editor.isActive("orderedList"), () => editor.chain().focus().toggleOrderedList().run(), <ListOrdered size={14} />, "Numbered list")}
      <div className="w-px bg-slate-200 mx-1" />
      <button
        type="button"
        title="Insert link"
        onClick={() => {
          const url = prompt("Enter URL");
          if (url) editor.chain().focus().setLink({ href: url }).run();
        }}
        className={`p-1.5 rounded hover:bg-slate-100 transition-colors ${editor.isActive("link") ? "bg-slate-200 text-slate-900" : "text-slate-500"}`}
      >
        <Link2 size={14} />
      </button>
      <button
        type="button"
        title="Insert image"
        onClick={() => imgInputRef.current?.click()}
        className="p-1.5 rounded hover:bg-slate-100 transition-colors text-slate-500"
      >
        <Image size={14} />
      </button>
      <input ref={imgInputRef} type="file" accept="image/*" className="hidden" onChange={handleImageUpload} />
    </div>
  );
}

function ArticleEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      ImageExt,
      LinkExt.configure({ openOnClick: false }),
      Placeholder.configure({ placeholder: "Write your article content here…" }),
    ],
    content: value,
    onUpdate({ editor }) {
      onChange(editor.getHTML());
    },
  });

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <RichTextToolbar editor={editor} />
      <EditorContent
        editor={editor}
        className="prose prose-sm max-w-none p-4 min-h-[300px] focus:outline-none [&_.tiptap]:outline-none [&_.tiptap]:min-h-[280px]"
      />
    </div>
  );
}

export function ArticlesTab() {
  const [subTab, setSubTab] = useState<"articles" | "templates" | "email-templates">("articles");
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
      const res = await api.get("/article-templates");
      setAvailableTemplates(res.data.templates || []);
    } catch { toast.error("Failed to load templates"); }
    finally { setLoadingTemplates(false); }
  };

  // Customer search for visibility typeahead
  const [custVisSearch, setCustVisSearch] = useState("");
  const [articles, setArticles] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingArticle, setEditingArticle] = useState<any>(null);
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const [articleLogs, setArticleLogs] = useState<any[]>([]);
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
      const res = await api.get(`/articles/admin/list?${params}`);
      setArticles(res.data.articles || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 1);
      setPage(p);
    } catch {
      toast.error("Failed to load articles");
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, searchFilter, startDate, endDate]);

  useEffect(() => { load(1); }, [categoryFilter, searchFilter, startDate, endDate]);

  const resetForm = () => setForm({ title: "", slug: "", category: "", price: "", content: "", visibility: "all", restricted_to: [] });

  const openCreate = () => {
    resetForm();
    setEditingArticle(null);
    setShowForm(true);
  };

  const openEdit = async (article: any) => {
    setEditingArticle(article);
    try {
      const res = await api.get(`/articles/${article.id}`);
      const a = res.data.article;
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
      toast.error("Failed to load article");
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
      toast.error("Price is required for Scope - Final articles");
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
      if (editingArticle) {
        await api.put(`/articles/${editingArticle.id}`, payload);
        toast.success("Article updated");
      } else {
        await api.post("/articles", payload);
        toast.success("Article created");
      }
      setShowForm(false);
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to save article");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this article? This cannot be undone.")) return;
    setDeleting(id);
    try {
      await api.delete(`/articles/${id}`);
      toast.success("Article deleted");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Delete failed");
    } finally {
      setDeleting(null);
    }
  };

  const handleViewLogs = async (article: any) => {
    try {
      const res = await api.get(`/articles/${article.id}/logs`);
      setArticleLogs(res.data.logs || []);
      setShowLogsDialog(true);
    } catch {
      toast.error("Failed to load logs");
    }
  };

  const handleEmailOpen = (article: any) => {
    setEmailTarget(article);
    setEmailForm({ to: [], cc: [], bcc: [], subject: `Article: ${article.title}`, html_body: "", attach_pdf: false });
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
      const res = await api.get("/article-email-templates");
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
      await api.post("/article-email-templates", {
        name,
        subject: emailForm.subject,
        html_body: emailForm.html_body,
        description: `For article: ${emailTarget?.title || ""}`,
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
      const res = await api.post(`/articles/${emailTarget.id}/send-email`, emailForm);
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
    fetch(`${base}/api/admin/export/articles?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `articles-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); })
      .catch(() => toast.error("Export failed"));
  };

  const downloadArticle = (articleId: string, format: "pdf" | "docx") => {
    const token = localStorage.getItem("aa_token");
    const base = process.env.REACT_APP_BACKEND_URL || "";
    fetch(`${base}/api/articles/${articleId}/download?format=${format}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob()).then(b => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(b);
        a.download = `article-${articleId.slice(0, 8)}.${format}`;
        a.click();
      }).catch(() => toast.error("Download failed"));
  };

  const saveAsTemplate = async (article: any) => {
    const name = prompt(`Save "${article.title}" as template. Template name:`, article.title);
    if (!name) return;
    try {
      const res = await api.get(`/articles/${article.id}`);
      const a = res.data.article;
      await api.post("/article-templates", {
        name,
        description: `Template created from article: ${a.title}`,
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
    <div className="space-y-4" data-testid="admin-articles-tab">
      <AdminPageHeader title="Articles" subtitle={subTab === "articles" ? `${total} articles` : "Manage reusable templates"} actions={
        <>
          {subTab === "articles" && (
            <>
              <Button size="sm" variant="outline" onClick={downloadCsv} data-testid="articles-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
              <Button size="sm" onClick={openCreate} className="gap-2" data-testid="articles-create-btn"><Plus size={14} /> New Article</Button>
            </>
          )}
        </>
      } />

      {/* Sub-tab switcher */}
      <div className="flex gap-1 border-b border-slate-200">
        <button onClick={() => setSubTab("articles")} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${subTab === "articles" ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700"}`} data-testid="subtab-articles">Articles</button>
        <button onClick={() => setSubTab("templates")} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${subTab === "templates" ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700"}`} data-testid="subtab-templates"><LayoutTemplate size={13} /> Templates</button>
        <button onClick={() => setSubTab("email-templates")} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${subTab === "email-templates" ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700"}`} data-testid="subtab-email-templates"><Mail size={13} /> Email Templates</button>
      </div>

      {/* Templates sub-tab */}
      {subTab === "templates" && <ArticleTemplatesTab />}

      {/* Email Templates sub-tab */}
      {subTab === "email-templates" && <ArticleEmailTemplatesTab />}

      {/* Articles sub-tab */}
      {subTab === "articles" && (<>

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Input placeholder="Search title or ID…" value={searchFilter} onChange={e => setSearchFilter(e.target.value)} className="h-8 text-xs w-44" data-testid="articles-search-filter" />
          <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)} className="h-8 border border-slate-200 rounded px-2 text-xs bg-white" data-testid="articles-category-filter">
            <option value="all">All categories</option>
            {ARTICLE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Created</span>
            <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="h-8 text-xs w-32" data-testid="articles-start-date" />
            <span className="text-xs text-slate-400">–</span>
            <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="h-8 text-xs w-32" data-testid="articles-end-date" />
          </div>
          <Button size="sm" variant="outline" onClick={() => { setSearchFilter(""); setCategoryFilter("all"); setStartDate(""); setEndDate(""); }} className="h-8 text-xs" data-testid="articles-clear-filters">Clear</Button>
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
              <TableHead className="text-xs">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-slate-400 py-8 text-sm">Loading…</TableCell>
              </TableRow>
            ) : articles.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-slate-400 py-8 text-sm">No articles yet.</TableCell>
              </TableRow>
            ) : articles.map((a) => (
              <TableRow key={a.id} data-testid={`article-row-${a.id}`}>
                <TableCell className="font-mono text-xs text-slate-500">{a.id?.slice(0, 8)}</TableCell>
                <TableCell className="text-xs text-slate-500 whitespace-nowrap">{a.created_at?.slice(0, 10)}</TableCell>
                <TableCell className="text-xs text-slate-500 whitespace-nowrap">{a.updated_at?.slice(0, 10)}</TableCell>
                <TableCell>
                  <div className="text-sm font-medium text-slate-900">{a.title}</div>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    a.category?.startsWith("Scope - Final") ? "bg-green-100 text-green-700" :
                    a.category === "Scope - Draft" ? "bg-amber-100 text-amber-700" :
                    "bg-slate-100 text-slate-600"
                  }`}>{a.category}</span>
                </TableCell>
                <TableCell className="text-sm font-medium text-slate-900">
                  {a.price ? `$${a.price}` : "—"}
                </TableCell>
                <TableCell className="text-xs text-slate-600">
                  {a.visibility === "all" || !a.restricted_to?.length ? "All" : `${a.restricted_to.length} customer(s)`}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1 flex-wrap">
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => openEdit(a)} data-testid={`article-edit-${a.id}`}>
                      Edit
                    </Button>
                    <a href={`${frontendUrl}/articles/${a.slug || a.id}`} target="_blank" rel="noreferrer">
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" data-testid={`article-view-${a.id}`}>
                        <ExternalLink size={10} /> View
                      </Button>
                    </a>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => downloadArticle(a.id, "pdf")} data-testid={`article-dl-pdf-${a.id}`}>
                      <FileText size={10} /> PDF
                    </Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => downloadArticle(a.id, "docx")} data-testid={`article-dl-docx-${a.id}`}>
                      <Download size={10} /> DOCX
                    </Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => saveAsTemplate(a)} data-testid={`article-save-template-${a.id}`}>
                      <LayoutTemplate size={10} /> Template
                    </Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => handleViewLogs(a)} data-testid={`article-logs-${a.id}`}>
                      <Clock size={10} /> Logs
                    </Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1" onClick={() => handleEmailOpen(a)} data-testid={`article-email-${a.id}`}>
                      <Mail size={10} /> Email
                    </Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1 text-red-500 hover:text-red-700" onClick={() => handleDelete(a.id)} disabled={deleting === a.id} data-testid={`article-delete-${a.id}`}>
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
      <Dialog open={showForm} onOpenChange={(o) => { setShowForm(o); if (!o) setEditingArticle(null); }}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="article-form-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between">
              <span>{editingArticle ? `Edit: ${editingArticle.title}` : "New Article"}</span>
              <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={() => { loadTemplates(); setShowTemplatePicker(true); }} data-testid="article-use-template-btn">
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
                  placeholder="Article title"
                  data-testid="article-title-input"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">Slug / URL</label>
                <Input
                  value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value })}
                  placeholder="auto-generated"
                  className="font-mono text-sm"
                  data-testid="article-slug-input"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">Category *</label>
                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v, price: SCOPE_FINAL.has(v) ? form.price : "" })}>
                  <SelectTrigger data-testid="article-category-select">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {ARTICLE_CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
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
                    data-testid="article-price-input"
                  />
                </div>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-700">Show this article to</label>
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
                    data-testid="article-customer-search"
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
              <Button onClick={handleSave} disabled={saving} data-testid="article-save-btn">
                {saving ? "Saving…" : editingArticle ? "Update Article" : "Create Article"}
              </Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Logs Dialog */}
      <Dialog open={showLogsDialog} onOpenChange={setShowLogsDialog}>
        <DialogContent className="max-w-lg" data-testid="article-logs-dialog">
          <DialogHeader><DialogTitle>Article Activity Log</DialogTitle></DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto space-y-2">
            {articleLogs.length === 0 ? (
              <p className="text-sm text-slate-500 py-4 text-center">No activity yet.</p>
            ) : articleLogs.map((log) => (
              <div key={log.id} className="border border-slate-200 rounded p-3 text-sm">
                <div className="flex justify-between items-start">
                  <span className="font-semibold text-slate-900 capitalize">{log.action.replace(/_/g, " ")}</span>
                  <span className="text-xs text-slate-400">{new Date(log.created_at).toLocaleString()}</span>
                </div>
                <div className="text-xs text-slate-500 mt-1">By: {log.actor}</div>
                {log.details && Object.keys(log.details).length > 0 && (
                  <pre className="text-xs text-slate-400 mt-1 bg-slate-50 p-2 rounded overflow-x-auto">
                    {JSON.stringify(log.details, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Email Dialog */}
      <Dialog open={showEmailDialog} onOpenChange={setShowEmailDialog}>
        <DialogContent className="max-w-md" data-testid="article-email-dialog">
          <DialogHeader><DialogTitle>Email Article: {emailTarget?.title}</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Customer(s) *</label>
              <select
                multiple
                className="w-full border border-slate-200 rounded p-2 text-sm h-32"
                value={emailForm.customer_ids}
                onChange={(e) => setEmailForm({ ...emailForm, customer_ids: Array.from(e.target.selectedOptions, (o) => o.value) })}
                data-testid="email-customer-select"
              >
                {customers.map((c: any) => (
                  <option key={c.id} value={c.id}>{c.email || c.company_name || c.full_name || c.id}</option>
                ))}
              </select>
              <p className="text-xs text-slate-400">{emailForm.customer_ids.length} selected</p>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Subject</label>
              <Input
                value={emailForm.subject}
                onChange={(e) => setEmailForm({ ...emailForm, subject: e.target.value })}
                data-testid="email-subject-input"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Message (optional)</label>
              <Textarea
                value={emailForm.message}
                onChange={(e) => setEmailForm({ ...emailForm, message: e.target.value })}
                rows={3}
                placeholder="Add a personal note…"
                data-testid="email-message-input"
              />
            </div>
            <Button className="w-full" onClick={handleSendEmail} disabled={savingEmail} data-testid="email-send-btn">
              {savingEmail ? "Sending…" : "Send Email"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Template Picker Dialog */}
      <Dialog open={showTemplatePicker} onOpenChange={setShowTemplatePicker}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto" data-testid="template-picker-dialog">
          <DialogHeader><DialogTitle>Choose a Template</DialogTitle></DialogHeader>
          <p className="text-xs text-slate-500 -mt-1 mb-3">Select a template to pre-fill the article content. Your title and category will be preserved.</p>
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
    </>) /* end articles sub-tab */}
    </div>
  );
}
