import { useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";
import { Eye, EyeOff, Save, X, ChevronDown, ChevronUp, Mail, AlertCircle, CheckCircle2, XCircle, Pencil } from "lucide-react";
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

interface SettingItem {
  key: string;
  value_json: any;
  is_secret?: boolean;
  value_type?: string;
  description?: string;
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

// ─── ProviderSection ─────────────────────────────────────────────────────────

const PROVIDER_EMAIL_KEYS = [
  "email_provider_enabled", "resend_api_key", "resend_sender_email",
  "email_reply_to", "email_cc", "email_bcc",
];

function SettingField({ label, value, onSave, isSecret, description, testId }: {
  label: string; value: string; onSave: (v: string) => Promise<void>;
  isSecret?: boolean; description?: string; testId?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(value);
  const [show, setShow] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try { await onSave(val); setEditing(false); setShow(false); } finally { setSaving(false); }
  };

  return (
    <div className="py-2 border-b border-slate-100 last:border-0">
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-slate-700">{label}</p>
          {description && <p className="text-[11px] text-slate-400">{description}</p>}
        </div>
        {!editing ? (
          <button onClick={() => { setVal(value); setEditing(true); }}
            className="ml-4 text-xs text-slate-600 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded px-2 py-1 max-w-48 truncate font-mono transition-colors" data-testid={testId}>
            {isSecret && value ? "••••••••" : value || <span className="text-slate-300 italic">not set</span>}
          </button>
        ) : (
          <div className="ml-4 flex items-center gap-1">
            <div className="relative">
              <Input type={isSecret && !show ? "password" : "text"} value={val} onChange={e => setVal(e.target.value)}
                className="h-7 text-xs w-64 pr-8 font-mono" autoFocus data-testid={`edit-${testId}`} />
              {isSecret && (
                <button type="button" onClick={() => setShow(!show)} className="absolute right-2 top-1.5 text-slate-400">
                  {show ? <EyeOff size={12} /> : <Eye size={12} />}
                </button>
              )}
            </div>
            <Button size="sm" className="h-7 px-2 text-xs" onClick={handleSave} disabled={saving}>
              {saving ? "…" : <Save size={11} />}
            </Button>
            <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setEditing(false)}>
              <X size={11} />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── ProviderSection (tile + inline slide) ───────────────────────────────────

function ProviderSection({ settings }: { settings: Record<string, SettingItem> }) {
  const [isEnabled, setIsEnabled] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [open, setOpen] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{success: boolean; message: string} | null>(null);

  useEffect(() => {
    const s = settings["email_provider_enabled"];
    setIsEnabled(s?.value_json === true || s?.value_json === "true");
  }, [settings]);

  const saveSetting = async (key: string, value: any) => {
    await api.put(`/admin/settings/key/${key}`, { value });
    toast.success("Saved");
  };

  const toggleProvider = async (enabled: boolean) => {
    setToggling(true);
    try {
      await api.put("/admin/settings/key/email_provider_enabled", { value: enabled });
      setIsEnabled(enabled);
      toast.success(enabled ? "Email provider enabled" : "Email provider disabled (mocked mode)");
    } catch { toast.error("Failed to update"); }
    finally { setToggling(false); }
  };

  const validateResend = async () => {
    setValidating(true);
    setValidationResult(null);
    try {
      const res = await api.post("/admin/integrations/resend/validate");
      setValidationResult(res.data);
      if (res.data.success) {
        toast.success("Resend connection validated");
      } else {
        toast.error(res.data.message || "Validation failed");
      }
    } catch (err: any) {
      setValidationResult({ success: false, message: err.response?.data?.detail || "Validation failed" });
      toast.error("Validation failed");
    } finally {
      setValidating(false);
    }
  };

  const fields: { key: string; label: string; isSecret?: boolean; description?: string }[] = [
    { key: "resend_api_key", label: "Resend API Key", isSecret: true, description: "Get from resend.com dashboard" },
    { key: "resend_sender_email", label: "From Email Address", description: "The email shown in the 'From' field" },
    { key: "email_reply_to", label: "Reply-to Email", description: "Optional: where replies are directed" },
    { key: "email_cc", label: "CC (all emails)", description: "Comma-separated — added to every outgoing email" },
    { key: "email_bcc", label: "BCC (all emails)", description: "Comma-separated — blind copied on every outgoing email" },
  ];

  return (
    <>
      {/* Tile */}
      <div
        className="rounded-xl border border-slate-200 bg-white p-4 flex items-center justify-between cursor-pointer hover:border-slate-300 transition-colors"
        data-testid="resend-provider-tile"
        onClick={() => setOpen(true)}
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-100">
            <Mail size={15} className="text-slate-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-800">Resend</p>
            <p className="text-xs text-slate-400 mt-0.5">Transactional email via resend.com</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs px-2 py-0.5 rounded-full ${isEnabled ? "text-emerald-700 bg-emerald-50" : "text-slate-500 bg-slate-100"}`}>
            {isEnabled ? "Live" : "Mocked"}
          </span>
          <Pencil size={14} className="text-slate-400" />
        </div>
      </div>

      {/* Slide panel */}
      {open && (
        <div className="fixed inset-0 z-50 flex justify-end" data-testid="resend-slide-panel">
          <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />
          <div className="relative z-10 w-full max-w-md bg-white shadow-xl flex flex-col h-full">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Resend Integration</h3>
                <p className="text-xs text-slate-400 mt-0.5">Configure transactional email via resend.com</p>
              </div>
              <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-600 p-1">
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              <div className="flex items-center justify-between py-3 border-b border-slate-100">
                <div>
                  <p className="text-sm font-medium text-slate-700">Email sending</p>
                  <p className="text-xs text-slate-400">{isEnabled ? "Live — emails are sent" : "Mocked — emails stored in outbox only"}</p>
                </div>
                <button role="switch" aria-checked={isEnabled} onClick={() => toggleProvider(!isEnabled)}
                  disabled={toggling} data-testid="toggle-email-provider"
                  className={`relative inline-flex h-5 w-9 items-center rounded-full border-2 border-transparent transition-colors focus:outline-none disabled:opacity-50 ${isEnabled ? "bg-emerald-500" : "bg-slate-200"}`}>
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${isEnabled ? "translate-x-4" : "translate-x-0"}`} />
                </button>
              </div>
              {fields.map(f => (
                <SettingField key={f.key} label={f.label} isSecret={f.isSecret} description={f.description}
                  value={String(settings[f.key]?.value_json ?? "")}
                  onSave={v => saveSetting(f.key, v)} testId={`email-${f.key}`} />
              ))}
              
              {/* Validate Button */}
              <div className="pt-4 border-t border-slate-100">
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={validateResend} 
                  disabled={validating}
                  data-testid="validate-resend-btn"
                  className="w-full"
                >
                  {validating ? "Validating..." : "Validate Connection"}
                </Button>
                {validationResult && (
                  <div className={`mt-2 flex items-start gap-2 rounded-lg px-3 py-2 ${validationResult.success ? "bg-emerald-50 border border-emerald-200" : "bg-red-50 border border-red-200"}`}>
                    {validationResult.success ? (
                      <CheckCircle2 size={14} className="text-emerald-500 mt-0.5 shrink-0" />
                    ) : (
                      <XCircle size={14} className="text-red-500 mt-0.5 shrink-0" />
                    )}
                    <p className={`text-xs ${validationResult.success ? "text-emerald-700" : "text-red-700"}`}>
                      {validationResult.message}
                    </p>
                  </div>
                )}
              </div>
              
              {!isEnabled && (
                <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                  <AlertCircle size={14} className="text-amber-500 mt-0.5 shrink-0" />
                  <p className="text-xs text-amber-700">Email provider is off — emails are stored in the outbox (not sent). Enable the toggle above to send live emails.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ─── Zoho Mail Provider Section ───────────────────────────────────────────────

function ZohoMailSection() {
  const [open, setOpen] = useState(false);
  const [datacenter, setDatacenter] = useState("US");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"connected" | "not_configured" | "error">("not_configured");
  const [validationResult, setValidationResult] = useState<any>(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const res = await api.get("/admin/integrations/status");
      const zoho = res.data.integrations?.zoho_mail;
      if (zoho?.status === "connected") {
        setConnectionStatus("connected");
        setDatacenter(zoho.datacenter || "US");
      }
    } catch {}
  };

  const saveCredentials = async () => {
    if (!clientId || !clientSecret) {
      toast.error("Client ID and Secret are required");
      return;
    }
    setSaving(true);
    try {
      await api.post("/admin/integrations/zoho-mail/save-credentials", {
        client_id: clientId,
        client_secret: clientSecret,
        datacenter
      });
      toast.success("Zoho Mail credentials saved");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const validateConnection = async () => {
    if (!accessToken) {
      toast.error("Access token required for validation");
      return;
    }
    setValidating(true);
    setValidationResult(null);
    try {
      const res = await api.post("/admin/integrations/zoho-mail/validate", {
        access_token: accessToken,
        datacenter
      });
      setValidationResult(res.data);
      if (res.data.success) {
        setConnectionStatus("connected");
        toast.success("Zoho Mail connected successfully");
      } else {
        setConnectionStatus("error");
        toast.error(res.data.message || "Validation failed");
      }
    } catch (err: any) {
      setConnectionStatus("error");
      setValidationResult({ success: false, message: err.response?.data?.detail || "Validation failed" });
      toast.error("Validation failed");
    } finally {
      setValidating(false);
    }
  };

  return (
    <>
      {/* Tile */}
      <div
        className="rounded-xl border border-slate-200 bg-white p-4 flex items-center justify-between cursor-pointer hover:border-slate-300 transition-colors mt-2"
        data-testid="zoho-mail-provider-tile"
        onClick={() => setOpen(true)}
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-orange-100">
            <Mail size={15} className="text-orange-600" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-800">Zoho Mail</p>
            <p className="text-xs text-slate-400 mt-0.5">Transactional email via Zoho Mail API</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs px-2 py-0.5 rounded-full ${connectionStatus === "connected" ? "text-emerald-700 bg-emerald-50" : "text-slate-500 bg-slate-100"}`}>
            {connectionStatus === "connected" ? `Connected (${datacenter})` : "Not Connected"}
          </span>
          <Pencil size={14} className="text-slate-400" />
        </div>
      </div>

      {/* Slide panel */}
      {open && (
        <div className="fixed inset-0 z-50 flex justify-end" data-testid="zoho-mail-slide-panel">
          <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />
          <div className="relative z-10 w-full max-w-md bg-white shadow-xl flex flex-col h-full">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Zoho Mail Integration</h3>
                <p className="text-xs text-slate-400 mt-0.5">Configure email via Zoho Mail API</p>
              </div>
              <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-600 p-1">
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {/* Datacenter selection */}
              <div>
                <label className="text-xs font-medium text-slate-700">Datacenter</label>
                <select 
                  value={datacenter} 
                  onChange={(e) => setDatacenter(e.target.value)}
                  className="mt-1 w-full h-9 px-3 text-sm border border-slate-200 rounded-md"
                  data-testid="zoho-mail-datacenter-select"
                >
                  <option value="US">United States (zoho.com)</option>
                  <option value="CA">Canada (zohocloud.ca)</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-700">Client ID</label>
                <Input 
                  value={clientId} 
                  onChange={(e) => setClientId(e.target.value)}
                  placeholder="Enter Zoho Client ID"
                  className="mt-1"
                  data-testid="zoho-mail-client-id"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-slate-700">Client Secret</label>
                <Input 
                  type="password"
                  value={clientSecret} 
                  onChange={(e) => setClientSecret(e.target.value)}
                  placeholder="Enter Zoho Client Secret"
                  className="mt-1"
                  data-testid="zoho-mail-client-secret"
                />
              </div>

              <Button onClick={saveCredentials} disabled={saving} size="sm" className="w-full">
                {saving ? "Saving..." : "Save Credentials"}
              </Button>

              <div className="border-t border-slate-100 pt-4">
                <label className="text-xs font-medium text-slate-700">Access Token</label>
                <Input 
                  value={accessToken} 
                  onChange={(e) => setAccessToken(e.target.value)}
                  placeholder="Paste access token from OAuth flow"
                  className="mt-1"
                  data-testid="zoho-mail-access-token"
                />
                <p className="text-[11px] text-slate-400 mt-1">Get this from Zoho API Console after OAuth authorization</p>
              </div>

              <Button 
                variant="outline" 
                onClick={validateConnection} 
                disabled={validating || !accessToken}
                size="sm"
                className="w-full"
                data-testid="validate-zoho-mail-btn"
              >
                {validating ? "Validating..." : "Validate Connection"}
              </Button>

              {validationResult && (
                <div className={`flex items-start gap-2 rounded-lg px-3 py-2 ${validationResult.success ? "bg-emerald-50 border border-emerald-200" : "bg-red-50 border border-red-200"}`}>
                  {validationResult.success ? (
                    <CheckCircle2 size={14} className="text-emerald-500 mt-0.5 shrink-0" />
                  ) : (
                    <XCircle size={14} className="text-red-500 mt-0.5 shrink-0" />
                  )}
                  <div>
                    <p className={`text-xs ${validationResult.success ? "text-emerald-700" : "text-red-700"}`}>
                      {validationResult.message}
                    </p>
                    {validationResult.accounts && (
                      <p className="text-[11px] text-slate-500 mt-1">
                        Accounts: {validationResult.accounts.map((a: any) => a.email).join(", ")}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
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
  const [emailSettings, setEmailSettings] = useState<Record<string, SettingItem>>({});
  const [logs, setLogs] = useState<EmailLog[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [showLogs, setShowLogs] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplate | null>(null);
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [integrationStatus, setIntegrationStatus] = useState<any>(null);
  const [settingActiveProvider, setSettingActiveProvider] = useState(false);

  const load = async () => {
    setLoadingTemplates(true);
    try {
      const [tmplRes, settingsRes, integRes] = await Promise.all([
        api.get("/admin/email-templates"),
        api.get("/admin/settings/structured"),
        api.get("/admin/integrations/status"),
      ]);
      setTemplates(tmplRes.data.templates || []);
      const emailItems: Record<string, SettingItem> = {};
      (settingsRes.data.settings?.Email || []).forEach((item: SettingItem) => {
        emailItems[item.key] = item;
      });
      setEmailSettings(emailItems);
      setActiveProvider(integRes.data.active_email_provider);
      setIntegrationStatus(integRes.data.integrations);
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

  const setProviderActive = async (provider: string) => {
    setSettingActiveProvider(true);
    try {
      await api.post("/admin/integrations/email-providers/set-active", { provider });
      setActiveProvider(provider === "none" ? null : provider);
      toast.success(
        provider === "none" 
          ? "Email sending disabled. All emails will be stored in outbox only." 
          : `${provider === "resend" ? "Resend" : "Zoho Mail"} is now your active email provider. The previous provider has been deactivated.`
      );
      load(); // Refresh to get updated status
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to set active provider");
    } finally {
      setSettingActiveProvider(false);
    }
  };

  const toggleTemplate = async (tmpl: EmailTemplate) => {
    if (!activeProvider) {
      toast.error("Please activate an email provider first before enabling templates");
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

  const resendValidated = integrationStatus?.resend?.is_validated;
  const zohoMailValidated = integrationStatus?.zoho_mail?.is_validated;

  return (
    <div data-testid="email-section">
      {/* Active Provider Alert */}
      {activeProvider && (
        <div className="mb-4 flex items-center gap-2 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3">
          <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
          <p className="text-sm text-emerald-700">
            <strong>{activeProvider === "resend" ? "Resend" : "Zoho Mail"}</strong> is your active email provider. 
            Emails will be sent through this service. Only one provider can be active at a time.
          </p>
        </div>
      )}
      {!activeProvider && (
        <div className="mb-4 flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
          <AlertCircle size={16} className="text-amber-600 shrink-0" />
          <p className="text-sm text-amber-700">
            <strong>No email provider active.</strong> Emails are stored in outbox but not sent. 
            Configure and activate a provider below to start sending emails.
          </p>
        </div>
      )}

      {/* Provider */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-slate-700 mb-1">Email Providers</h3>
        <p className="text-xs text-slate-400 mb-3">
          Configure your email provider. Only one provider can be active at a time. 
          When you activate a new provider, the previous one is automatically deactivated.
        </p>
        <ProviderSection 
          settings={emailSettings} 
          isActive={activeProvider === "resend"}
          isValidated={resendValidated}
          onSetActive={() => setProviderActive("resend")}
          onDeactivate={() => setProviderActive("none")}
          settingActive={settingActiveProvider}
          onRefresh={load}
        />
        <ZohoMailSection 
          isActive={activeProvider === "zoho_mail"}
          isValidated={zohoMailValidated}
          onSetActive={() => setProviderActive("zoho_mail")}
          onDeactivate={() => setProviderActive("none")}
          settingActive={settingActiveProvider}
          onRefresh={load}
        />
      </div>

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
