import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import {
  MessageSquare, X, Plus, ChevronDown, Loader2, Clock, User, Building2,
  Phone, Mail, Send,
} from "lucide-react";
import api from "@/lib/api";

const STATUSES = ["Pending", "Not Started", "Working", "Future", "Rejected", "Completed"] as const;
type Status = typeof STATUSES[number];

const STATUS_COLORS: Record<Status, string> = {
  Pending:      "bg-amber-50 text-amber-700 border-amber-200",
  "Not Started": "bg-slate-50 text-slate-600 border-slate-200",
  Working:      "bg-blue-50 text-blue-700 border-blue-200",
  Future:       "bg-purple-50 text-purple-700 border-purple-200",
  Rejected:     "bg-red-50 text-red-700 border-red-200",
  Completed:    "bg-green-50 text-green-700 border-green-200",
};

interface IntegrationRequest {
  id: string;
  partner_name: string;
  partner_code: string;
  submitted_by_name: string;
  contact_email: string;
  contact_phone: string;
  phone_country_code: string;
  integration_name: string;
  description: string;
  status: Status;
  notes: Array<{ id: string; text: string; created_at: string; created_by_name: string }>;
  created_at: string;
}

export function IntegrationRequestsTab() {
  const [requests, setRequests] = useState<IntegrationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [notesOpen, setNotesOpen] = useState<string | null>(null);
  const [newNote, setNewNote] = useState("");
  const [addingNote, setAddingNote] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get("/integration-requests");
      setRequests(res.data.integration_requests || []);
    } catch {
      toast.error("Failed to load integration requests");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateStatus = async (id: string, status: string) => {
    setUpdatingStatus(id);
    try {
      const res = await api.put(`/integration-requests/${id}/status`, { status });
      setRequests(rs => rs.map(r => r.id === id ? res.data.integration_request : r));
      toast.success("Status updated");
    } catch {
      toast.error("Failed to update status");
    } finally {
      setUpdatingStatus(null);
    }
  };

  const addNote = async (id: string) => {
    if (!newNote.trim()) return;
    setAddingNote(true);
    try {
      const res = await api.post(`/integration-requests/${id}/notes`, { text: newNote.trim() });
      setRequests(rs => rs.map(r => r.id === id ? res.data.integration_request : r));
      setNewNote("");
      toast.success("Note added");
    } catch {
      toast.error("Failed to add note");
    } finally {
      setAddingNote(false);
    }
  };

  const formatDate = (iso: string) =>
    iso ? new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "—";

  const formatTime = (iso: string) =>
    iso ? new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Integration Requests</h2>
        <p className="text-sm text-slate-500 mt-1">
          Submitted by partner organisations. Update status and add internal notes.
        </p>
      </div>

      {requests.length === 0 ? (
        <div className="text-center py-16 text-slate-400 bg-white rounded-xl border border-slate-200">
          <MessageSquare className="mx-auto mb-3 opacity-30" size={32} />
          <p className="text-sm font-medium">No integration requests yet</p>
          <p className="text-xs mt-1">Requests submitted by partners will appear here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {requests.map(req => {
            const isNotesOpen = notesOpen === req.id;
            const statusColor = STATUS_COLORS[req.status as Status] || "bg-slate-50 text-slate-600 border-slate-200";

            return (
              <div key={req.id} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`ir-row-${req.id}`}>
                {/* Main row */}
                <div className="p-5">
                  <div className="flex items-start justify-between gap-4">
                    {/* Left: info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <h3 className="font-semibold text-slate-900 text-sm">{req.integration_name}</h3>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${statusColor}`}>
                          {req.status}
                        </span>
                      </div>
                      {req.description && (
                        <p className="text-xs text-slate-500 mb-3 leading-relaxed">{req.description}</p>
                      )}

                      {/* Partner info row */}
                      <div className="flex items-center gap-4 flex-wrap text-xs text-slate-500">
                        <span className="flex items-center gap-1.5">
                          <Building2 size={11} className="text-slate-400" />
                          <span className="font-medium text-slate-700">{req.partner_name || req.partner_code}</span>
                          <span className="text-slate-300">·</span>
                          <code className="text-slate-400 font-mono">{req.partner_code}</code>
                        </span>
                        <span className="flex items-center gap-1.5">
                          <User size={11} className="text-slate-400" />
                          {req.submitted_by_name || "—"}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <Mail size={11} className="text-slate-400" />
                          <a href={`mailto:${req.contact_email}`} className="hover:text-blue-600 transition-colors">
                            {req.contact_email}
                          </a>
                        </span>
                        {req.contact_phone && (
                          <span className="flex items-center gap-1.5">
                            <Phone size={11} className="text-slate-400" />
                            {req.phone_country_code} {req.contact_phone}
                          </span>
                        )}
                        <span className="flex items-center gap-1.5 text-slate-400">
                          <Clock size={11} />
                          {formatDate(req.created_at)}
                        </span>
                      </div>
                    </div>

                    {/* Right: status + notes */}
                    <div className="flex items-center gap-2 shrink-0">
                      {/* Status dropdown */}
                      <div className="relative">
                        {updatingStatus === req.id ? (
                          <div className="h-8 w-28 flex items-center justify-center">
                            <Loader2 size={14} className="animate-spin text-slate-400" />
                          </div>
                        ) : (
                          <Select value={req.status} onValueChange={v => updateStatus(req.id, v)}>
                            <SelectTrigger
                              className="h-8 text-xs w-36"
                              data-testid={`ir-status-${req.id}`}
                            >
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {STATUSES.map(s => (
                                <SelectItem key={s} value={s} className="text-xs">{s}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      </div>

                      {/* Notes toggle */}
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8 text-xs gap-1.5"
                        onClick={() => setNotesOpen(isNotesOpen ? null : req.id)}
                        data-testid={`ir-notes-btn-${req.id}`}
                      >
                        <MessageSquare size={12} />
                        Notes {req.notes.length > 0 && <span className="bg-slate-100 text-slate-600 rounded-full px-1.5 py-0.5 text-[10px] font-semibold">{req.notes.length}</span>}
                        <ChevronDown size={12} className={`transition-transform ${isNotesOpen ? "rotate-180" : ""}`} />
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Notes panel */}
                {isNotesOpen && (
                  <div className="border-t border-slate-100 bg-slate-50 px-5 py-4 space-y-3">
                    {/* Existing notes */}
                    {req.notes.length === 0 ? (
                      <p className="text-xs text-slate-400 italic">No notes yet.</p>
                    ) : (
                      <div className="space-y-2">
                        {req.notes.map(note => (
                          <div key={note.id} className="bg-white border border-slate-200 rounded-lg px-3 py-2.5">
                            <p className="text-xs text-slate-700 leading-relaxed">{note.text}</p>
                            <p className="text-[10px] text-slate-400 mt-1.5">
                              {note.created_by_name} · {formatTime(note.created_at)}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Add new note */}
                    <div className="flex gap-2">
                      <Textarea
                        value={newNote}
                        onChange={e => setNewNote(e.target.value)}
                        placeholder="Add an internal note…"
                        className="text-xs min-h-[64px] resize-none"
                        onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) addNote(req.id); }}
                        data-testid={`ir-note-input-${req.id}`}
                      />
                      <Button
                        size="sm"
                        onClick={() => addNote(req.id)}
                        disabled={addingNote || !newNote.trim()}
                        className="h-8 self-end shrink-0 gap-1.5"
                        data-testid={`ir-note-submit-${req.id}`}
                      >
                        {addingNote ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                        Add
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
