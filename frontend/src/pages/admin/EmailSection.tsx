import { useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";
import { X, ChevronDown, ChevronUp, Mail, AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import api from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

interface EmailTemplate {
  id: string;
  trigger: string;
  label: string;
  description: string;
  subject: string;
  html_body: string;
  is_enabled: boolean;
  available_variables: string[];
  is_system: boolean;
}

interface EmailLog {
  id: string;
  trigger: string;
  recipient: string;
  subject: string;
  status: string;
  provider: string;
  error_message?: string;
  created_at: string;
}

// ─── Rich Text Editor ─────────────────────────────────────────────────────────

function ToolBtn({ active, onClick, title, children }: { active?: boolean; onClick: () => void; title: string; children: React.ReactNode }) {
  return (
    <button type="button" title={title} onClick={onClick}
      className={`px-2 py-1 text-xs rounded transition-colors ${active ? "bg-slate-900 text-white" : "hover:bg-slate-200 text-slate-700"}`}>
      {children}
    </button>
  );
}

function RichTextEditor({ value, onChange }: { value: string; onChange: (html: string) => void }) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Link.configure({ openOnClick: false }),
    ],
    content: value,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  });

  // Re-sync content when value changes externally (e.g. variable insertion)
  useEffect(() => {
    if (editor && !editor.isDestroyed && editor.getHTML() !== value) {
      editor.commands.setContent(value);
    }
  }, [value, editor]);

  if (!editor) return null;

  const setLink = () => {
    const url = prompt("Enter URL:");
    if (url) editor.chain().focus().setLink({ href: url }).run();
    else editor.chain().focus().unsetLink().run();
  };

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <div className="flex flex-wrap gap-0.5 p-2 bg-slate-50 border-b border-slate-200">
        <ToolBtn active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()} title="Bold"><strong>B</strong></ToolBtn>
        <ToolBtn active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()} title="Italic"><em>I</em></ToolBtn>
        <ToolBtn active={editor.isActive("strike")} onClick={() => editor.chain().focus().toggleStrike().run()} title="Strikethrough"><s>S</s></ToolBtn>
        <span className="w-px bg-slate-200 mx-1" />
        <ToolBtn active={editor.isActive("heading", { level: 1 })} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} title="Heading 1">H1</ToolBtn>
        <ToolBtn active={editor.isActive("heading", { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} title="Heading 2">H2</ToolBtn>
        <ToolBtn active={editor.isActive("heading", { level: 3 })} onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} title="Heading 3">H3</ToolBtn>
        <span className="w-px bg-slate-200 mx-1" />
        <ToolBtn active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()} title="Bullet list">• List</ToolBtn>
        <ToolBtn active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()} title="Numbered list">1. List</ToolBtn>
        <ToolBtn active={editor.isActive("blockquote")} onClick={() => editor.chain().focus().toggleBlockquote().run()} title="Blockquote">"</ToolBtn>
        <span className="w-px bg-slate-200 mx-1" />
        <ToolBtn active={editor.isActive("link")} onClick={setLink} title="Set link">Link</ToolBtn>
        <ToolBtn active={false} onClick={() => editor.chain().focus().unsetLink().run()} title="Remove link">Unlink</ToolBtn>
        <span className="w-px bg-slate-200 mx-1" />
        <ToolBtn active={false} onClick={() => editor.chain().focus().undo().run()} title="Undo">↩</ToolBtn>
        <ToolBtn active={false} onClick={() => editor.chain().focus().redo().run()} title="Redo">↪</ToolBtn>
      </div>
      <EditorContent editor={editor}
        className="prose prose-sm max-w-none p-3 min-h-[280px] outline-none focus-within:outline-none" />
    </div>
  );
}

// ─── Template Editor ──────────────────────────────────────────────────────────

function TemplateEditor({ template, onSave, onClose }: {
  template: EmailTemplate;
  onSave: (id: string, data: any) => void;
  onClose: () => void;
}) {
  const [subject, setSubject] = useState(template.subject);
  const [htmlBody, setHtmlBody] = useState(template.html_body);
  const [tab, setTab] = useState<"rich" | "html" | "preview">("rich");
  const [saving, setSaving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const insertVar = (v: string) => {
    if (tab === "html") {
      const ta = textareaRef.current;
      if (!ta) return;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const newVal = htmlBody.slice(0, start) + v + htmlBody.slice(end);
      setHtmlBody(newVal);
      setTimeout(() => { ta.focus(); ta.selectionStart = ta.selectionEnd = start + v.length; }, 0);
    } else {
      // For rich text and preview, just append to htmlBody
      setHtmlBody(prev => prev + v);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/admin/email-templates/${template.id}`, { subject, html_body: htmlBody });
      toast.success("Template saved");
      onSave(template.id, { subject, html_body: htmlBody });
    } catch { toast.error("Save failed"); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <div>
            <h3 className="font-semibold text-slate-900">{template.label}</h3>
            <p className="text-xs text-slate-400 mt-0.5">{template.description}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1"><X size={18} /></button>
        </div>

        <div className="p-5 overflow-y-auto flex-1 space-y-4">
          {/* Subject */}
          <div>
            <label className="text-xs font-medium text-slate-700">Subject line</label>
            <Input value={subject} onChange={e => setSubject(e.target.value)} className="mt-1" data-testid="template-subject-input" />
          </div>

          {/* Available variables */}
          {template.available_variables?.length > 0 && (
            <div>
              <p className="text-xs text-slate-500 mb-1.5">Available variables — click to insert at cursor:</p>
              <div className="flex flex-wrap gap-1.5">
                {template.available_variables.map(v => (
                  <button key={v} type="button" onClick={() => insertVar(v)}
                    className="text-[11px] font-mono bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded hover:bg-blue-100 transition-colors">
                    {v}
                  </button>
                ))}
                <button type="button" onClick={() => insertVar("{{ref:key_name}}")}
                  className="text-[11px] font-mono bg-purple-50 text-purple-700 border border-purple-100 px-2 py-0.5 rounded hover:bg-purple-100 transition-colors">
                  {"{{ref:key_name}}"}
                </button>
              </div>
            </div>
          )}

          {/* Editor tabs */}
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <div className="flex border-b border-slate-200 bg-slate-50">
              {(["rich", "html", "preview"] as const).map(t => (
                <button key={t} onClick={() => setTab(t)}
                  className={`px-4 py-2 text-xs font-medium transition-colors ${tab === t ? "text-slate-900 bg-white border-b-2 border-slate-900" : "text-slate-500 hover:text-slate-700"}`}>
                  {t === "rich" ? "Rich Text" : t === "html" ? "HTML Source" : "Preview"}
                </button>
              ))}
            </div>
            {tab === "rich" && (
              <div className="p-2">
                <RichTextEditor key="rich-editor" value={htmlBody} onChange={setHtmlBody} />
              </div>
            )}
            {tab === "html" && (
              <textarea ref={textareaRef} value={htmlBody} onChange={e => setHtmlBody(e.target.value)}
                className="w-full h-72 p-3 text-xs font-mono text-slate-700 outline-none resize-none bg-white"
                spellCheck={false} data-testid="template-html-editor" />
            )}
            {tab === "preview" && (
              <div
                contentEditable
                suppressContentEditableWarning
                onInput={(e) => setHtmlBody(e.currentTarget.innerHTML)}
                className="h-72 overflow-auto bg-white p-4 prose prose-sm max-w-none outline-none focus:outline-none"
                data-testid="template-html-preview"
                dangerouslySetInnerHTML={{ __html: htmlBody }}
              />
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 p-4 border-t border-slate-100">
          <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={handleSave} disabled={saving} data-testid="save-template-btn">
            {saving ? "Saving…" : "Save Template"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── EmailSection ─────────────────────────────────────────────────────────────

export default function EmailSection() {
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [logs, setLogs] = useState<EmailLog[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [showLogs, setShowLogs] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplate | null>(null);
  const [activeProvider, setActiveProvider] = useState<string | null>(null);

  const load = async () => {
    setLoadingTemplates(true);
    try {
      const [tmplRes, integRes] = await Promise.all([
        api.get("/admin/email-templates"),
        api.get("/admin/integrations/status"),
      ]);
      setTemplates(tmplRes.data.templates || []);
      setActiveProvider(integRes.data.active_email_provider);
    } catch { toast.error("Failed to load email settings"); }
    finally { setLoadingTemplates(false); }
  };

  const loadLogs = async () => {
    try {
      const res = await api.get("/admin/email-logs?limit=30");
      setLogs(res.data.logs || []);
    } catch {}
  };

  useEffect(() => { load(); }, []);
  useEffect(() => { if (showLogs) loadLogs(); }, [showLogs]);

  const toggleTemplate = async (tmpl: EmailTemplate) => {
    if (!activeProvider) {
      toast.error("Please connect and activate an email provider in Connect Services first");
      return;
    }
    try {
      await api.put(`/admin/email-templates/${tmpl.id}`, { is_enabled: !tmpl.is_enabled });
      setTemplates(prev => prev.map(t => t.id === tmpl.id ? { ...t, is_enabled: !t.is_enabled } : t));
      toast.success(tmpl.is_enabled ? "Template disabled" : "Template enabled");
    } catch { toast.error("Failed to toggle"); }
  };

  const onTemplateSaved = (id: string, data: any) => {
    setTemplates(prev => prev.map(t => t.id === id ? { ...t, ...data } : t));
    setEditingTemplate(null);
  };

  if (loadingTemplates) return <div className="text-slate-400 text-sm">Loading…</div>;

  return (
    <div data-testid="email-section">
      {/* Active Provider Status */}
      {activeProvider && (
        <div className="mb-4 flex items-center justify-between bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
            <p className="text-sm text-emerald-700">
              <strong>{activeProvider === "resend" ? "Resend" : "Zoho Mail"}</strong> is your active email provider.
            </p>
          </div>
          <a href="/admin?tab=integrations" className="text-xs text-emerald-700 hover:text-emerald-800 underline">
            Manage in Connect Services →
          </a>
        </div>
      )}
      {!activeProvider && (
        <div className="mb-4 flex items-center justify-between bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="text-amber-600 shrink-0" />
            <p className="text-sm text-amber-700">
              <strong>No email provider active.</strong> Emails are stored but not sent.
            </p>
          </div>
          <a href="/admin?tab=integrations" className="text-xs text-amber-700 hover:text-amber-800 underline font-medium">
            Connect a Provider →
          </a>
        </div>
      )}

      {/* Templates */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-1">Email Templates</h3>
        <p className="text-xs text-slate-400 mb-3">Configure the email sent for each event. Toggle on/off to enable or disable each email.</p>
        <div className="space-y-2">
          {templates.map(tmpl => (
            <div key={tmpl.id} className={`rounded-xl border p-4 transition-colors ${tmpl.is_enabled ? "border-slate-200 bg-white" : "border-slate-100 bg-slate-50"}`}>
              <div className="flex items-start gap-3">
                <div className="mt-0.5 p-2 rounded-lg bg-slate-100">
                  <Mail size={14} className="text-slate-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`font-medium text-sm ${tmpl.is_enabled ? "text-slate-800" : "text-slate-400"}`}>{tmpl.label}</span>
                    <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">{tmpl.trigger}</span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5 truncate">{tmpl.description}</p>
                  {tmpl.is_enabled && (
                    <p className="text-[11px] text-slate-500 mt-1 font-mono">Subject: {tmpl.subject}</p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => setEditingTemplate(tmpl)}
                    className="text-xs text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 px-2.5 py-1 rounded transition-colors"
                    data-testid={`edit-template-${tmpl.trigger}`}>
                    Edit
                  </button>
                  <button role="switch" aria-checked={tmpl.is_enabled} onClick={() => toggleTemplate(tmpl)}
                    data-testid={`toggle-template-${tmpl.trigger}`}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full border-2 border-transparent transition-colors ${tmpl.is_enabled ? "bg-emerald-500" : "bg-slate-200"}`}>
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${tmpl.is_enabled ? "translate-x-4" : "translate-x-0"}`} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Email Logs */}
      <div className="mt-6 border border-slate-200 rounded-xl overflow-hidden">
        <button onClick={() => setShowLogs(!showLogs)} className="w-full flex items-center justify-between px-5 py-3.5 bg-slate-50 hover:bg-slate-100 transition-colors">
          <span className="text-sm font-medium text-slate-700">Email Logs</span>
          {showLogs ? <ChevronUp size={15} className="text-slate-400" /> : <ChevronDown size={15} className="text-slate-400" />}
        </button>
        {showLogs && (
          <div className="overflow-x-auto">
            {logs.length === 0 ? (
              <p className="text-sm text-slate-400 p-4">No email logs yet.</p>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200">
                    <th className="text-left px-4 py-2 text-slate-500 font-medium">Trigger</th>
                    <th className="text-left px-4 py-2 text-slate-500 font-medium">Recipient</th>
                    <th className="text-left px-4 py-2 text-slate-500 font-medium">Subject</th>
                    <th className="text-left px-4 py-2 text-slate-500 font-medium">Provider</th>
                    <th className="text-left px-4 py-2 text-slate-500 font-medium">Status</th>
                    <th className="text-left px-4 py-2 text-slate-500 font-medium">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => (
                    <tr key={log.id} className="border-b border-slate-100 last:border-0">
                      <td className="px-4 py-2.5 font-mono text-slate-600">{log.trigger}</td>
                      <td className="px-4 py-2.5 text-slate-600">{log.recipient}</td>
                      <td className="px-4 py-2.5 text-slate-600 max-w-xs truncate">{log.subject}</td>
                      <td className="px-4 py-2.5">
                        <span className="text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{log.provider}</span>
                      </td>
                      <td className="px-4 py-2.5">
                        {log.status === "sent" ? <CheckCircle2 size={13} className="text-emerald-500" /> :
                          log.status === "failed" ? <XCircle size={13} className="text-red-500" aria-label={log.error_message} /> :
                          <span className="text-slate-400">{log.status}</span>}
                      </td>
                      <td className="px-4 py-2.5 text-slate-400">{new Date(log.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Template editor modal */}
      {editingTemplate && (
        <TemplateEditor template={editingTemplate} onSave={onTemplateSaved} onClose={() => setEditingTemplate(null)} />
      )}
    </div>
  );
}
// timestamp 1771886620
