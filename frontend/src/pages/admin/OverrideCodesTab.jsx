import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const STATUS_COLORS = {
  active: "bg-emerald-100 text-emerald-700 border border-emerald-200",
  inactive: "bg-slate-100 text-slate-500 border border-slate-200",
  expired: "bg-red-100 text-red-600 border border-red-200",
};

export default function OverrideCodesTab() {
  const [codes, setCodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [customers, setCustomers] = useState([]);
  const [editingCode, setEditingCode] = useState(null);

  const [createForm, setCreateForm] = useState({ code: "", customer_id: "", expires_at: "" });
  const [editForm, setEditForm] = useState({ code: "", customer_id: "", status: "", expires_at: "" });

  const fetchCodes = async () => {
    try {
      const params = {};
      if (filterStatus) params.status = filterStatus;
      const res = await api.get("/admin/override-codes", { params });
      setCodes(res.data.override_codes || []);
    } catch {
      toast.error("Failed to load override codes");
    } finally {
      setLoading(false);
    }
  };

  const fetchCustomers = async () => {
    try {
      const [custRes, userRes] = await Promise.all([
        api.get("/admin/customers"),
        api.get("/admin/users"),
      ]);
      const custs = custRes.data.customers || custRes.data || [];
      const users = userRes.data.users || userRes.data || [];
      const options = custs.map((c) => {
        const u = users.find((u) => u.id === c.user_id) || {};
        return { customer_id: c.id, email: u.email || c.user_id, name: u.full_name || "" };
      });
      setCustomers(options);
    } catch {
      // ignore
    }
  };

  useEffect(() => { fetchCodes(); }, [filterStatus]);
  useEffect(() => { fetchCustomers(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!createForm.code.trim() || !createForm.customer_id) {
      toast.error("Code and customer are required");
      return;
    }
    try {
      await api.post("/admin/override-codes", {
        code: createForm.code.trim(),
        customer_id: createForm.customer_id,
        expires_at: createForm.expires_at ? new Date(createForm.expires_at).toISOString() : undefined,
      });
      toast.success("Override code created");
      setCreateForm({ code: "", customer_id: "", expires_at: "" });
      setShowCreate(false);
      fetchCodes();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to create override code");
    }
  };

  const openEdit = (oc) => {
    setEditingCode(oc);
    setEditForm({
      code: oc.code,
      customer_id: oc.customer_id,
      status: oc.status,
      expires_at: oc.expires_at ? oc.expires_at.slice(0, 16) : "",
    });
  };

  const handleEdit = async (e) => {
    e.preventDefault();
    if (!editingCode) return;
    try {
      const updates = {};
      if (editForm.code !== editingCode.code) updates.code = editForm.code;
      if (editForm.customer_id !== editingCode.customer_id) updates.customer_id = editForm.customer_id;
      if (editForm.status !== editingCode.status) updates.status = editForm.status;
      if (editForm.expires_at && editForm.expires_at !== editingCode.expires_at?.slice(0, 16))
        updates.expires_at = new Date(editForm.expires_at).toISOString();
      await api.put(`/admin/override-codes/${editingCode.id}`, updates);
      toast.success("Override code updated");
      setEditingCode(null);
      fetchCodes();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to update override code");
    }
  };

  const handleDeactivate = async (id) => {
    if (!confirm("Deactivate this override code?")) return;
    try {
      await api.delete(`/admin/override-codes/${id}`);
      toast.success("Override code deactivated");
      fetchCodes();
    } catch {
      toast.error("Failed to deactivate");
    }
  };

  const filtered = filterStatus ? codes.filter((c) => c.effective_status === filterStatus) : codes;

  return (
    <div data-testid="override-codes-tab" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Override Codes</h2>
          <p className="text-sm text-slate-400 mt-0.5">
            Customer-specific codes allowing checkout without Zoho Partner tagging
          </p>
        </div>
        <Button
          data-testid="create-override-code-btn"
          onClick={() => setShowCreate(!showCreate)}
          className="bg-[#0e1a2e] border border-slate-600 hover:bg-[#162234] text-white"
        >
          {showCreate ? "Cancel" : "+ New Code"}
        </Button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <form
          onSubmit={handleCreate}
          data-testid="create-override-code-form"
          className="bg-[#0e1a2e] border border-slate-700 rounded-xl p-5 space-y-4"
        >
          <h3 className="text-sm font-semibold text-white">New Override Code</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1">
              <label className="text-slate-300 text-xs block">Code *</label>
              <Input
                data-testid="override-code-input"
                value={createForm.code}
                onChange={(e) => setCreateForm({ ...createForm, code: e.target.value })}
                placeholder="e.g. PARTNER-2026-ABC"
                className="bg-[#162234] border-slate-600 text-white"
              />
            </div>
            <div className="space-y-1">
              <label className="text-slate-300 text-xs block">Customer *</label>
              <select
                data-testid="override-customer-select"
                value={createForm.customer_id}
                onChange={(e) => setCreateForm({ ...createForm, customer_id: e.target.value })}
                className="w-full h-10 bg-[#162234] border border-slate-600 text-white rounded-md px-3 text-sm"
              >
                <option value="">Select customer...</option>
                {customers.map((c) => (
                  <option key={c.customer_id} value={c.customer_id}>
                    {c.email}{c.name ? ` — ${c.name}` : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-slate-300 text-xs block">Expires At (default: 48h)</label>
              <Input
                data-testid="override-expires-input"
                type="datetime-local"
                value={createForm.expires_at}
                onChange={(e) => setCreateForm({ ...createForm, expires_at: e.target.value })}
                className="bg-[#162234] border-slate-600 text-white"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button type="submit" data-testid="submit-override-code-btn" className="bg-slate-700 hover:bg-slate-600 text-white">
              Create Code
            </Button>
            <Button type="button" variant="ghost" onClick={() => setShowCreate(false)} className="text-slate-400">
              Cancel
            </Button>
          </div>
        </form>
      )}

      {/* Edit Modal */}
      {editingCode && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
          <form
            onSubmit={handleEdit}
            className="bg-[#0e1a2e] border border-slate-700 rounded-xl p-6 w-full max-w-lg space-y-4 shadow-2xl"
          >
            <h3 className="text-sm font-semibold text-white">Edit Override Code</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-slate-300 text-xs block">Code</label>
                <Input
                  value={editForm.code}
                  onChange={(e) => setEditForm({ ...editForm, code: e.target.value })}
                  className="bg-[#162234] border-slate-600 text-white"
                />
              </div>
              <div className="space-y-1">
                <label className="text-slate-300 text-xs block">Customer</label>
                <select
                  value={editForm.customer_id}
                  onChange={(e) => setEditForm({ ...editForm, customer_id: e.target.value })}
                  className="w-full h-10 bg-[#162234] border border-slate-600 text-white rounded-md px-3 text-sm"
                >
                  {customers.map((c) => (
                    <option key={c.customer_id} value={c.customer_id}>
                      {c.email}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-slate-300 text-xs block">Status</label>
                <select
                  value={editForm.status}
                  onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                  className="w-full h-10 bg-[#162234] border border-slate-600 text-white rounded-md px-3 text-sm"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-slate-300 text-xs block">Expires At</label>
                <Input
                  type="datetime-local"
                  value={editForm.expires_at}
                  onChange={(e) => setEditForm({ ...editForm, expires_at: e.target.value })}
                  className="bg-[#162234] border-slate-600 text-white"
                />
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <Button type="submit" className="bg-slate-700 hover:bg-slate-600 text-white">Save Changes</Button>
              <Button type="button" variant="ghost" onClick={() => setEditingCode(null)} className="text-slate-400">Cancel</Button>
            </div>
          </form>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {["", "active", "inactive", "expired"].map((s) => (
          <button
            key={s}
            data-testid={`filter-status-${s || "all"}`}
            onClick={() => setFilterStatus(s)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              filterStatus === s
                ? "bg-slate-200 text-slate-800 border border-slate-400"
                : "text-slate-500 hover:text-slate-800 border border-transparent"
            }`}
          >
            {s ? s.charAt(0).toUpperCase() + s.slice(1) : "All"}
          </button>
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <p className="text-slate-400 text-sm">Loading...</p>
      ) : filtered.length === 0 ? (
        <p className="text-slate-500 text-sm py-8 text-center">No override codes found.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                {["Code", "Customer", "Status", "Created", "Expires", "Used At", "Order", "Actions"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((oc) => (
                <tr key={oc.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3">
                    <code className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-xs font-mono">{oc.code}</code>
                  </td>
                  <td className="px-4 py-3 text-slate-600 text-xs">
                    <div>{oc.customer_email || oc.customer_id?.slice(0, 8)}</div>
                    {oc.customer_name && <div className="text-slate-400">{oc.customer_name}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[oc.effective_status] || STATUS_COLORS.inactive}`}>
                      {oc.effective_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">{new Date(oc.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-slate-500 text-xs">{oc.expires_at ? new Date(oc.expires_at).toLocaleString() : "—"}</td>
                  <td className="px-4 py-3 text-slate-500 text-xs">{oc.used_at ? new Date(oc.used_at).toLocaleString() : "—"}</td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {oc.used_for_order_id ? <code className="text-slate-600 text-xs">{oc.used_for_order_id.slice(0, 8)}</code> : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        data-testid={`edit-override-code-${oc.id}`}
                        onClick={() => openEdit(oc)}
                        className="text-xs text-slate-500 hover:text-slate-800 underline transition-colors"
                      >Edit</button>
                      {oc.effective_status === "active" && (
                        <button
                          data-testid={`deactivate-override-code-${oc.id}`}
                          onClick={() => handleDeactivate(oc.id)}
                          className="text-xs text-red-500 hover:text-red-700 underline transition-colors"
                        >Deactivate</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
