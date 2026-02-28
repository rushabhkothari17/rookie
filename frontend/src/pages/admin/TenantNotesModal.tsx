import { useState, useEffect } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Trash2, StickyNote, Plus } from "lucide-react";

type Note = {
  id: string;
  text: string;
  created_by: string;
  created_at: string;
};

type Props = {
  tenantId: string;
  tenantName: string;
  onClose: () => void;
};

export function TenantNotesModal({ tenantId, tenantName, onClose }: Props) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [newNote, setNewNote] = useState("");
  const [adding, setAdding] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/admin/tenants/${tenantId}/notes`);
      setNotes(data.notes || []);
    } catch {
      toast.error("Failed to load notes");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [tenantId]);

  const handleAdd = async () => {
    if (!newNote.trim()) return;
    setAdding(true);
    try {
      await api.post(`/admin/tenants/${tenantId}/notes`, { text: newNote.trim() });
      setNewNote("");
      toast.success("Note added");
      load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to add note");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (noteId: string) => {
    try {
      await api.delete(`/admin/tenants/${tenantId}/notes/${noteId}`);
      toast.success("Note deleted");
      setNotes(n => n.filter(x => x.id !== noteId));
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to delete note");
    }
  };

  const fmt = (iso: string) => {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <StickyNote className="h-5 w-5 text-amber-500" />
            Notes — {tenantName}
          </DialogTitle>
        </DialogHeader>

        {/* Add Note */}
        <div className="space-y-2 mt-2">
          <Textarea
            placeholder="Add an internal note about this partner…"
            rows={3}
            value={newNote}
            onChange={e => setNewNote(e.target.value)}
            data-testid="new-note-input"
          />
          <Button
            size="sm"
            onClick={handleAdd}
            disabled={adding || !newNote.trim()}
            data-testid="add-note-btn"
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            {adding ? "Adding…" : "Add Note"}
          </Button>
        </div>

        {/* Notes List */}
        <div className="mt-4 space-y-3">
          {loading ? (
            <p className="text-sm text-slate-400 text-center py-4">Loading…</p>
          ) : notes.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-4">No notes yet.</p>
          ) : (
            notes.map(note => (
              <div key={note.id} className="flex gap-3 p-3 bg-amber-50 rounded-lg border border-amber-100">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{note.text}</p>
                  <p className="text-xs text-slate-400 mt-1">
                    {note.created_by} · {fmt(note.created_at)}
                  </p>
                </div>
                <button
                  onClick={() => handleDelete(note.id)}
                  className="text-slate-400 hover:text-red-500 transition-colors mt-0.5"
                  data-testid={`delete-note-${note.id}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
