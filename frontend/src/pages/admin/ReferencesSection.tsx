import { useEffect, useState, useCallback } from "react";
import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import { Plus, Pencil, Trash2, Copy, X, Save } from "lucide-react";
import api from "@/lib/api";

const REF_TYPES = [
  { value: "url", label: "URL / Link" },
  { value: "email", label: "Email address" },
  { value: "phone", label: "Phone number" },
  { value: "text", label: "Text / Label" },
  { value: "custom", label: "Custom" },
];

interface Ref {
  id: string;
  key: string;
  label: string;
  type: string;
  value: string;
  description?: string;
  system?: boolean;
}

interface SystemItem {
  key: string;
  description: string;
  value_json: any;
  value_type: string;
}

const EMPTY: Partial<Ref> = { key: "", label: "", type: "text", value: "", description: "" };

function slugify(str: string): string {
  return str.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

function formatSystemLabel(key: string, description: string): string {
  if (description) return description;
  return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

interface Props {
  systemItems?: SystemItem[];
  onSystemItemSave?: (key: string, value: string) => Promise<void>;
}

export default function ReferencesSection({ systemItems = [], onSystemItemSave }: Props) {
  const [refs, setRefs] = useState<Ref[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingSystemKey, setEditingSystemKey] = useState<string | null>(null);
  const [systemDraftValue, setSystemDraftValue] = useState("");
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<Partial<Ref>>(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/references");
      setRefs(res.data.references || []);
    } catch { toast.error("Failed to load references"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const startEdit = (ref: Ref) => { setEditingId(ref.id); setDraft({ ...ref }); setCreating(false); setEditingSystemKey(null); };
  const startCreate = () => { setCreating(true); setEditingId(null); setDraft(EMPTY); setEditingSystemKey(null); };
  const cancel = () => { setCreating(false); setEditingId(null); setDraft(EMPTY); setEditingSystemKey(null); };

  const startEditSystem = (item: SystemItem) => {
    setEditingSystemKey(item.key);
    setSystemDraftValue(String(item.value_json ?? ""));
    setEditingId(null);
    setCreating(false);
  };

  const saveSystem = async (item: SystemItem) => {
    if (!onSystemItemSave) return;
    setSaving(true);
    try {
      await onSystemItemSave(item.key, systemDraftValue);
      setEditingSystemKey(null);
    } finally { setSaving(false); }
  };

  const save = async () => {
    if (!draft.label || !draft.key) { toast.error("Label and key are required"); return; }
    setSaving(true);
    try {
      if (creating) {
        await api.post("/admin/references", draft);
        toast.success("Reference created");
      } else {
        await api.put(`/admin/references/${editingId}`, draft);
        toast.success("Reference updated");
      }
      cancel();
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  };

  const deleteRef = async (ref: Ref) => {
    if (!confirm(`Delete reference '${ref.key}'?`)) return;
    try {
      await api.delete(`/admin/references/${ref.id}`);
      toast.success("Deleted");
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(`{{ref:${key}}}`);
    toast.success(`Copied: {{ref:${key}}}`);
  };

  const hasRows = systemItems.length > 0 || refs.length > 0;

  if (loading) return <div className="text-slate-400 text-sm">Loading…</div>;

  return (
    <div data-testid="references-section">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-700">References</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Store reusable values and insert them using{" "}
            <code className="bg-slate-100 text-slate-600 px-1 rounded font-mono text-[11px]">{"{{ref:key_name}}"}</code>
            {" "}in email templates, content, and forms.
          </p>
        </div>
        <Button size="sm" onClick={startCreate} data-testid="create-reference-btn">
          <Plus size={13} className="mr-1" /> New Reference
        </Button>
      </div>

      {/* Create form */}
      {creating && (
        <div className="mb-4 rounded-xl border border-blue-100 bg-blue-50/40 p-4">
          <p className="text-xs font-semibold text-blue-700 mb-3">Create new reference</p>
          <ReferenceForm draft={draft} setDraft={setDraft} />
          <div className="flex gap-2 mt-3">
            <Button size="sm" onClick={save} disabled={saving} data-testid="save-reference-btn">
              <Save size={12} className="mr-1" />{saving ? "Saving…" : "Save"}
            </Button>
            <Button size="sm" variant="ghost" onClick={cancel}><X size={12} className="mr-1" />Cancel</Button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="rounded-xl border border-slate-200 overflow-hidden">
        {!hasRows ? (
          <div className="py-10 text-center text-slate-400 text-sm">
            No references yet. Create one to start using <code>{"{{ref:key_name}}"}</code> in your content.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">Label</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">Key</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">Type</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">Value</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 w-24"></th>
              </tr>
            </thead>
            <tbody>
              {/* System (Zoho) rows */}
              {systemItems.map(item => (
                <React.Fragment key={`sys_${item.key}`}>
                  <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors bg-slate-50/50">
                    <td className="px-4 py-3">
                      <span className="font-medium text-slate-800">{formatSystemLabel(item.key, item.description)}</span>
                      <span className="ml-2 text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">system</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded">{item.key}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{item.value_type || "url"}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-600 max-w-xs truncate text-xs">
                      {item.value_json ? (
                        <a href={String(item.value_json)} target="_blank" rel="noopener noreferrer"
                          className="text-blue-600 hover:underline truncate block max-w-[200px]">
                          {String(item.value_json)}
                        </a>
                      ) : <span className="text-slate-400 italic">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => startEditSystem(item)}
                          className="p-1.5 text-slate-400 hover:text-blue-600 rounded"
                          data-testid={`edit-sysref-${item.key}`}>
                          <Pencil size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {editingSystemKey === item.key && (
                    <tr className="bg-blue-50/30 border-b border-slate-200">
                      <td colSpan={5} className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex-1">
                            <label className="text-xs text-slate-600 font-medium block mb-1">Value</label>
                            <Input value={systemDraftValue} onChange={e => setSystemDraftValue(e.target.value)}
                              placeholder="https://..." className="h-8 text-sm" data-testid={`sysref-value-${item.key}`} />
                          </div>
                          <div className="flex gap-2 mt-5">
                            <Button size="sm" onClick={() => saveSystem(item)} disabled={saving}>
                              <Save size={12} className="mr-1" />{saving ? "Saving…" : "Save"}
                            </Button>
                            <Button size="sm" variant="ghost" onClick={cancel}><X size={12} className="mr-1" />Cancel</Button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}

              {/* Custom reference rows */}
              {refs.map(ref => (
                <React.Fragment key={ref.id}>
                  <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-slate-800">{ref.label}</span>
                      </div>
                      {ref.description && <p className="text-[11px] text-slate-400 mt-0.5">{ref.description}</p>}
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => copyKey(ref.key)} title="Click to copy reference syntax"
                        className="flex items-center gap-1 font-mono text-xs text-blue-600 hover:text-blue-800 bg-blue-50 px-2 py-1 rounded transition-colors"
                        data-testid={`copy-ref-${ref.key}`}>
                        <span>{`{{ref:${ref.key}}}`}</span>
                        <Copy size={10} />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{ref.type}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-600 max-w-xs truncate text-xs">
                      {ref.type === "email" ? (
                        <a href={`mailto:${ref.value}`} className="text-blue-600 hover:underline">{ref.value}</a>
                      ) : ref.type === "url" ? (
                        <a href={ref.value} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate block max-w-[200px]">{ref.value}</a>
                      ) : ref.value}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => startEdit(ref)} className="p-1.5 text-slate-400 hover:text-blue-600 rounded" data-testid={`edit-ref-${ref.key}`}>
                          <Pencil size={13} />
                        </button>
                        <button onClick={() => deleteRef(ref)} className="p-1.5 text-slate-400 hover:text-red-500 rounded" data-testid={`delete-ref-${ref.key}`}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {editingId === ref.id && (
                    <tr className="bg-slate-50 border-b border-slate-200">
                      <td colSpan={5} className="px-4 py-4">
                        <ReferenceForm draft={draft} setDraft={setDraft} lockKey={ref.system} />
                        <div className="flex gap-2 mt-3">
                          <Button size="sm" onClick={save} disabled={saving} data-testid={`save-edit-ref-${ref.key}`}>
                            <Save size={12} className="mr-1" />{saving ? "Saving…" : "Save Changes"}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={cancel}><X size={12} className="mr-1" />Cancel</Button>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function ReferenceForm({ draft, setDraft, lockKey }: {
  draft: Partial<Ref>;
  setDraft: (d: Partial<Ref>) => void;
  lockKey?: boolean;
}) {
  const set = (key: keyof Ref, value: string) => setDraft({ ...draft, [key]: value });

  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="text-xs text-slate-600 font-medium">Label</label>
        <Input value={draft.label || ""} onChange={e => {
          const label = e.target.value;
          setDraft({ ...draft, label, key: lockKey ? draft.key : slugify(label) });
        }} placeholder="Contact Email" className="mt-0.5 h-8 text-sm" data-testid="ref-label-input" />
      </div>
      <div>
        <label className="text-xs text-slate-600 font-medium">Key {lockKey && <span className="text-amber-500">(locked)</span>}</label>
        <Input value={draft.key || ""} onChange={e => set("key", e.target.value)} placeholder="contact_email"
          disabled={lockKey} className="mt-0.5 h-8 text-sm font-mono" data-testid="ref-key-input" />
      </div>
      <div>
        <label className="text-xs text-slate-600 font-medium">Type</label>
        <Select value={draft.type || "text"} onValueChange={v => set("type", v)}>
          <SelectTrigger className="mt-0.5 h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            {REF_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div>
        <label className="text-xs text-slate-600 font-medium">Value</label>
        <Input value={draft.value || ""} onChange={e => set("value", e.target.value)}
          placeholder={draft.type === "email" ? "support@company.com" : draft.type === "url" ? "https://..." : draft.type === "phone" ? "+1 (555) 000-0000" : "Value"}
          type={draft.type === "email" ? "email" : draft.type === "url" ? "url" : "text"}
          className="mt-0.5 h-8 text-sm" data-testid="ref-value-input" />
      </div>
      <div className="col-span-2">
        <label className="text-xs text-slate-600 font-medium">Description (optional)</label>
        <Input value={draft.description || ""} onChange={e => set("description", e.target.value)}
          placeholder="Short description of this reference" className="mt-0.5 h-8 text-sm" data-testid="ref-description-input" />
      </div>
    </div>
  );
}

const REF_TYPES = [
  { value: "url", label: "URL / Link" },
  { value: "email", label: "Email address" },
  { value: "phone", label: "Phone number" },
  { value: "text", label: "Text / Label" },
  { value: "custom", label: "Custom" },
];

interface Ref {
  id: string;
  key: string;
  label: string;
  type: string;
  value: string;
  description?: string;
  system?: boolean;
}

const EMPTY: Partial<Ref> = { key: "", label: "", type: "text", value: "", description: "" };

function slugify(str: string): string {
  return str.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

export default function ReferencesSection() {
  const [refs, setRefs] = useState<Ref[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<Partial<Ref>>(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/references");
      setRefs(res.data.references || []);
    } catch { toast.error("Failed to load references"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const startEdit = (ref: Ref) => {
    setEditingId(ref.id);
    setDraft({ ...ref });
    setCreating(false);
  };

  const startCreate = () => {
    setCreating(true);
    setEditingId(null);
    setDraft(EMPTY);
  };

  const cancel = () => { setCreating(false); setEditingId(null); setDraft(EMPTY); };

  const save = async () => {
    if (!draft.label || !draft.key) { toast.error("Label and key are required"); return; }
    setSaving(true);
    try {
      if (creating) {
        await api.post("/admin/references", draft);
        toast.success("Reference created");
      } else {
        await api.put(`/admin/references/${editingId}`, draft);
        toast.success("Reference updated");
      }
      cancel();
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  };

  const deleteRef = async (ref: Ref) => {
    if (!confirm(`Delete reference '${ref.key}'?`)) return;
    try {
      await api.delete(`/admin/references/${ref.id}`);
      toast.success("Deleted");
      load();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(`{{ref:${key}}}`);
    toast.success(`Copied: {{ref:${key}}}`);
  };

  if (loading) return <div className="text-slate-400 text-sm">Loading…</div>;

  return (
    <div data-testid="references-section">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-700">References</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Store reusable values (URLs, emails, phone numbers, text) and insert them anywhere using{" "}
            <code className="bg-slate-100 text-slate-600 px-1 rounded font-mono text-[11px]">{"{{ref:key_name}}"}</code>
            {" "}— in email templates, website content, forms, and more.
          </p>
        </div>
        <Button size="sm" onClick={startCreate} data-testid="create-reference-btn">
          <Plus size={13} className="mr-1" /> New Reference
        </Button>
      </div>

      {/* Create form */}
      {creating && (
        <div className="mb-4 rounded-xl border border-blue-100 bg-blue-50/40 p-4">
          <p className="text-xs font-semibold text-blue-700 mb-3">Create new reference</p>
          <ReferenceForm draft={draft} setDraft={setDraft} />
          <div className="flex gap-2 mt-3">
            <Button size="sm" onClick={save} disabled={saving} data-testid="save-reference-btn">
              <Save size={12} className="mr-1" />{saving ? "Saving…" : "Save"}
            </Button>
            <Button size="sm" variant="ghost" onClick={cancel}>
              <X size={12} className="mr-1" />Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="rounded-xl border border-slate-200 overflow-hidden">
        {refs.length === 0 ? (
          <div className="py-10 text-center text-slate-400 text-sm">
            No references yet. Create one to start using <code>{"{{ref:key_name}}"}</code> in your content.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">Label</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">Key</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">Type</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">Value</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 w-24"></th>
              </tr>
            </thead>
            <tbody>
              {refs.map(ref => (
                <React.Fragment key={ref.id}>
                  <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-slate-800">{ref.label}</span>
                      </div>
                      {ref.description && <p className="text-[11px] text-slate-400 mt-0.5">{ref.description}</p>}
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => copyKey(ref.key)} title="Click to copy reference syntax" className="flex items-center gap-1 font-mono text-xs text-blue-600 hover:text-blue-800 bg-blue-50 px-2 py-1 rounded transition-colors" data-testid={`copy-ref-${ref.key}`}>
                        <span>{`{{ref:${ref.key}}}`}</span>
                        <Copy size={10} />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{ref.type}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-600 max-w-xs truncate text-xs">
                      {ref.type === "email" ? (
                        <a href={`mailto:${ref.value}`} className="text-blue-600 hover:underline">{ref.value}</a>
                      ) : ref.type === "url" ? (
                        <a href={ref.value} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate block max-w-[200px]">{ref.value}</a>
                      ) : ref.value}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => startEdit(ref)} className="p-1.5 text-slate-400 hover:text-blue-600 rounded" data-testid={`edit-ref-${ref.key}`}>
                          <Pencil size={13} />
                        </button>
                        <button onClick={() => deleteRef(ref)} className="p-1.5 text-slate-400 hover:text-red-500 rounded" data-testid={`delete-ref-${ref.key}`}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {editingId === ref.id && (
                    <tr className="bg-slate-50 border-b border-slate-200">
                      <td colSpan={5} className="px-4 py-4">
                        <ReferenceForm draft={draft} setDraft={setDraft} lockKey={ref.system} />
                        <div className="flex gap-2 mt-3">
                          <Button size="sm" onClick={save} disabled={saving} data-testid={`save-edit-ref-${ref.key}`}>
                            <Save size={12} className="mr-1" />{saving ? "Saving…" : "Save Changes"}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={cancel}><X size={12} className="mr-1" />Cancel</Button>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function ReferenceForm({ draft, setDraft, lockKey }: {
  draft: Partial<Ref>;
  setDraft: (d: Partial<Ref>) => void;
  lockKey?: boolean;
}) {
  const set = (key: keyof Ref, value: string) => setDraft({ ...draft, [key]: value });

  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="text-xs text-slate-600 font-medium">Label</label>
        <Input value={draft.label || ""} onChange={e => {
          const label = e.target.value;
          setDraft({ ...draft, label, key: lockKey ? draft.key : slugify(label) });
        }} placeholder="Contact Email" className="mt-0.5 h-8 text-sm" data-testid="ref-label-input" />
      </div>
      <div>
        <label className="text-xs text-slate-600 font-medium">Key {lockKey && <span className="text-amber-500">(locked)</span>}</label>
        <Input value={draft.key || ""} onChange={e => set("key", e.target.value)} placeholder="contact_email"
          disabled={lockKey} className="mt-0.5 h-8 text-sm font-mono" data-testid="ref-key-input" />
      </div>
      <div>
        <label className="text-xs text-slate-600 font-medium">Type</label>
        <Select value={draft.type || "text"} onValueChange={v => set("type", v)}>
          <SelectTrigger className="mt-0.5 h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            {REF_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div>
        <label className="text-xs text-slate-600 font-medium">Value</label>
        <Input value={draft.value || ""} onChange={e => set("value", e.target.value)}
          placeholder={draft.type === "email" ? "support@company.com" : draft.type === "url" ? "https://..." : draft.type === "phone" ? "+1 (555) 000-0000" : "Value"}
          type={draft.type === "email" ? "email" : draft.type === "url" ? "url" : "text"}
          className="mt-0.5 h-8 text-sm" data-testid="ref-value-input" />
      </div>
      <div className="col-span-2">
        <label className="text-xs text-slate-600 font-medium">Description (optional)</label>
        <Input value={draft.description || ""} onChange={e => set("description", e.target.value)}
          placeholder="Short description of this reference" className="mt-0.5 h-8 text-sm" data-testid="ref-description-input" />
      </div>
    </div>
  );
}
