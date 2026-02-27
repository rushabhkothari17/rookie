import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Plus, FileText, Pencil, Trash2, Star } from "lucide-react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import FormSchemaBuilder from "@/components/FormSchemaBuilder";
import SlideOver from "@/components/admin/SlideOver";
import { useWebsite } from "@/contexts/WebsiteContext";

interface CustomForm {
  id: string;
  name: string;
  schema: string;
  created_at: string;
  updated_at: string;
}

function fieldCount(schema: string): number {
  try { return JSON.parse(schema || "[]").length; } catch { return 0; }
}

export function FormsManagementTab() {
  const ws = useWebsite();
  const [forms, setForms] = useState<CustomForm[]>([]);
  const [loading, setLoading] = useState(true);

  // Slide-over for editing Default Form
  const [defaultSlideOpen, setDefaultSlideOpen] = useState(false);
  const [defaultSchema, setDefaultSchema] = useState(ws.scope_form_schema || "");
  const [defaultTitle, setDefaultTitle] = useState(ws.scope_form_title || "");
  const [defaultSubtitle, setDefaultSubtitle] = useState(ws.scope_form_subtitle || "");
  const [savingDefault, setSavingDefault] = useState(false);

  // Dialog for creating / editing a custom form
  const [formDialog, setFormDialog] = useState<{ open: boolean; form: CustomForm | null }>({ open: false, form: null });
  const [formName, setFormName] = useState("");
  const [formSchema, setFormSchema] = useState("[]");
  const [savingForm, setSavingForm] = useState(false);

  // Slide-over for editing a custom form schema
  const [editSlide, setEditSlide] = useState<{ open: boolean; form: CustomForm | null }>({ open: false, form: null });
  const [editSchema, setEditSchema] = useState("[]");
  const [editName, setEditName] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<CustomForm | null>(null);

  const loadForms = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/forms");
      setForms(res.data.forms || []);
    } catch {
      toast.error("Failed to load forms");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadForms(); }, [loadForms]);

  // Sync default form values when ws changes
  useEffect(() => {
    setDefaultSchema(ws.scope_form_schema || "");
    setDefaultTitle(ws.scope_form_title || "");
    setDefaultSubtitle(ws.scope_form_subtitle || "");
  }, [ws.scope_form_schema, ws.scope_form_title, ws.scope_form_subtitle]);

  const handleSaveDefault = async () => {
    setSavingDefault(true);
    try {
      await api.put("/admin/website-settings", {
        scope_form_schema: defaultSchema,
        scope_form_title: defaultTitle,
        scope_form_subtitle: defaultSubtitle,
      });
      toast.success("Default form saved");
      setDefaultSlideOpen(false);
    } catch {
      toast.error("Failed to save default form");
    } finally {
      setSavingDefault(false);
    }
  };

  const openCreate = () => {
    setFormName("");
    setFormDialog({ open: true, form: null });
  };

  const openEdit = (form: CustomForm) => {
    setEditName(form.name);
    setEditSchema(form.schema || "[]");
    setEditSlide({ open: true, form });
  };

  const handleCreate = async () => {
    if (!formName.trim()) { toast.error("Form name is required"); return; }
    setSavingForm(true);
    try {
      await api.post("/admin/forms", { name: formName.trim(), form_schema: "[]" });
      toast.success("Form created");
      setFormDialog({ open: false, form: null });
      loadForms();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to create form");
    } finally {
      setSavingForm(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editSlide.form) return;
    if (!editName.trim()) { toast.error("Form name is required"); return; }
    setSavingEdit(true);
    try {
      await api.put(`/admin/forms/${editSlide.form.id}`, { name: editName.trim(), form_schema: editSchema });
      toast.success("Form saved");
      setEditSlide({ open: false, form: null });
      loadForms();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to save form");
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDelete = async (form: CustomForm) => {
    try {
      await api.delete(`/admin/forms/${form.id}`);
      toast.success("Form deleted");
      loadForms();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to delete form");
    }
    setDeleteTarget(null);
  };

  return (
    <div className="space-y-6" data-testid="forms-management-tab">
      <AdminPageHeader
        title="Forms"
        subtitle="Manage enquiry forms used across your product catalogue."
        actions={
          <Button size="sm" onClick={openCreate} data-testid="create-form-btn">
            <Plus size={14} className="mr-1.5" /> Create Form
          </Button>
        }
      />

      {/* Default Form */}
      <div>
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Default Form</p>
        <div className="rounded-xl border-2 border-blue-200 bg-blue-50 p-5 flex items-start gap-4">
          <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center shrink-0">
            <Star size={18} className="text-blue-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-slate-800">Default Enquiry Form</p>
            <p className="text-xs text-slate-500 mt-0.5">
              Used by all products unless overridden — {fieldCount(ws.scope_form_schema)} field(s)
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setDefaultSchema(ws.scope_form_schema || "");
              setDefaultTitle(ws.scope_form_title || "");
              setDefaultSubtitle(ws.scope_form_subtitle || "");
              setDefaultSlideOpen(true);
            }}
            data-testid="edit-default-form-btn"
          >
            <Pencil size={13} className="mr-1.5" /> Edit
          </Button>
        </div>
      </div>

      {/* Custom Forms */}
      <div>
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Custom Forms ({forms.length})
        </p>
        {loading ? (
          <p className="text-sm text-slate-400 py-4">Loading…</p>
        ) : forms.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center">
            <FileText size={28} className="text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-slate-500">No custom forms yet.</p>
            <p className="text-xs text-slate-400 mt-1">Create a form to use it on specific enquiry products.</p>
            <Button size="sm" variant="outline" className="mt-4" onClick={openCreate} data-testid="create-form-empty-btn">
              <Plus size={13} className="mr-1" /> Create your first form
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {forms.map(form => (
              <div
                key={form.id}
                className="rounded-xl border border-slate-200 bg-white p-4 flex items-center gap-4"
                data-testid={`form-row-${form.id}`}
              >
                <div className="h-9 w-9 rounded-lg bg-slate-100 flex items-center justify-center shrink-0">
                  <FileText size={16} className="text-slate-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-800 text-sm">{form.name}</p>
                  <p className="text-xs text-slate-400">{fieldCount(form.schema)} field(s)</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => openEdit(form)}
                    data-testid={`edit-form-${form.id}`}
                  >
                    <Pencil size={12} className="mr-1" /> Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-red-500 hover:text-red-700"
                    onClick={() => setDeleteTarget(form)}
                    data-testid={`delete-form-${form.id}`}
                  >
                    <Trash2 size={12} className="mr-1" /> Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Form Dialog */}
      <Dialog open={formDialog.open} onOpenChange={open => !open && setFormDialog({ open: false, form: null })}>
        <DialogContent className="max-w-sm" data-testid="create-form-dialog">
          <DialogHeader>
            <DialogTitle>Create Form</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5 block">
                Form Name <span className="text-red-500">*</span>
              </label>
              <Input
                value={formName}
                onChange={e => setFormName(e.target.value)}
                placeholder="e.g. Project Brief"
                data-testid="new-form-name-input"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFormDialog({ open: false, form: null })}>Cancel</Button>
            <Button onClick={handleCreate} disabled={savingForm} data-testid="save-new-form-btn">
              {savingForm ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Custom Form SlideOver */}
      <SlideOver
        open={editSlide.open}
        onClose={() => setEditSlide({ open: false, form: null })}
        title={`Edit Form: ${editSlide.form?.name || ""}`}
        description="Modify the form fields used when customers submit this enquiry."
        onSave={handleSaveEdit}
        saving={savingEdit}
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5 block">Form Name</label>
            <Input value={editName} onChange={e => setEditName(e.target.value)} data-testid="edit-form-name-input" />
          </div>
          <div className="border-t border-slate-100 pt-3">
            <FormSchemaBuilder title="Form Fields" value={editSchema} onChange={setEditSchema} />
          </div>
        </div>
      </SlideOver>

      {/* Edit Default Form SlideOver */}
      <SlideOver
        open={defaultSlideOpen}
        onClose={() => setDefaultSlideOpen(false)}
        title="Default Enquiry Form"
        description="This form is used for all enquiry products unless a custom form is specified."
        onSave={handleSaveDefault}
        saving={savingDefault}
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5 block">Form Title</label>
            <Input value={defaultTitle} onChange={e => setDefaultTitle(e.target.value)} placeholder="Request a Quote" data-testid="default-form-title" />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5 block">Subtitle</label>
            <Input value={defaultSubtitle} onChange={e => setDefaultSubtitle(e.target.value)} placeholder="Tell us about your project..." data-testid="default-form-subtitle" />
          </div>
          <div className="border-t border-slate-100 pt-3">
            <FormSchemaBuilder title="Form Fields" value={defaultSchema} onChange={setDefaultSchema} />
          </div>
        </div>
      </SlideOver>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={open => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Form</AlertDialogTitle>
            <AlertDialogDescription>
              Delete "{deleteTarget?.name}"? This cannot be undone. Products using this form will fall back to the Default Form.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={() => deleteTarget && handleDelete(deleteTarget)}
              data-testid="confirm-delete-form-btn"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
