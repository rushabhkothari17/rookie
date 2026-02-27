import { useEffect, useState } from "react";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import api from "@/lib/api";
import { parseSchema, getAddressConfig } from "@/components/FormSchemaBuilder";
import { Download, Lock, Trash2, AlertTriangle } from "lucide-react";

function validatePhone(phone: string) {
  if (!phone) return "";
  const clean = phone.replace(/[\s\-().+]/g, "");
  if (!/^\d{7,15}$/.test(clean)) return "Enter a valid phone number (7–15 digits)";
  return "";
}

export default function Profile() {
  const { user, customer, address, refresh } = useAuth();
  const ws = useWebsite();
  const isAdmin = user?.role && ["partner_admin", "platform_admin", "admin"].includes(user.role);
  const [tenantCountry, setTenantCountry] = useState<string>("");
  const [form, setForm] = useState({
    full_name: "",
    company_name: "",
    phone: "",
    line1: "",
    line2: "",
    city: "",
    region: "",
    postal: "",
    country: "",
  });
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteReason, setDeleteReason] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [provinces, setProvinces] = useState<{ value: string; label: string }[]>([]);
  const [countries, setCountries] = useState<{ value: string; label: string }[]>([]);
  const [phoneError, setPhoneError] = useState("");

  // Derive address config and field visibility from signup schema
  const schema = parseSchema(ws.signup_form_schema);
  const schemaFields = Object.fromEntries(schema.map((f: any) => [f.key, f]));
  const phoneRequired = schemaFields["phone"]?.required ?? true;
  const companyRequired = schemaFields["company_name"]?.required ?? false;
  const addrSchemaField = schemaFields["address"];
  const addrVisible = !addrSchemaField || addrSchemaField.enabled !== false;
  const addrCfg = addrSchemaField ? getAddressConfig(addrSchemaField) : null;
  const sf = (key: string) => addrCfg ? (addrCfg as any)[key] : { enabled: true, required: true };

  useEffect(() => {
    if (!user) return;
    setForm({
      full_name: user.full_name || "",
      company_name: user.company_name || "",
      phone: user.phone || "",
      line1: address?.line1 || "",
      line2: address?.line2 || "",
      city: address?.city || "",
      region: address?.region || "",
      postal: address?.postal || "",
      country: address?.country || "",
    });
    // For admins, fetch their tenant's country from tax settings
    if (isAdmin) {
      api.get("/admin/taxes/settings").then(r => {
        const country = r.data.tax_settings?.country || "";
        setTenantCountry(country);
      }).catch(() => {});
    }
  }, [user, address, isAdmin]);

  // Fetch countries from taxes module on mount
  useEffect(() => {
    api.get("/utils/countries")
      .then(r => setCountries(r.data.countries || []))
      .catch(() => setCountries([{ value: "Canada", label: "Canada" }, { value: "USA", label: "United States" }]));
  }, []);

  // Fetch provinces/states when country changes
  useEffect(() => {
    const country = form.country;
    if (country) {
      api.get(`/utils/provinces?country_code=${encodeURIComponent(country)}`).then(r => {
        setProvinces(r.data.regions || []);
      }).catch(() => setProvinces([]));
    } else {
      setProvinces([]);
    }
  }, [form.country]);

  const handleChange = (key: string, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleExportData = async () => {
    setExporting(true);
    try {
      const response = await api.get("/me/data-export/download", {
        responseType: "blob"
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "my_data_export.zip");
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Data export downloaded");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    try {
      await api.post("/me/request-deletion", {
        reason: deleteReason,
        confirm: true
      });
      toast.success("Account deleted. You will be logged out.");
      setTimeout(() => {
        window.location.href = "/login";
      }, 2000);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Deletion failed");
      setDeleting(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    try {
      await api.put("/me", {
        full_name: form.full_name,
        company_name: form.company_name,
        phone: form.phone,
        address: {
          line1: form.line1,
          line2: form.line2,
          city: form.city,
          region: form.region,
          postal: form.postal,
          country: form.country,
        },
      });
      await refresh();
      toast.success("Profile updated");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Update failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="profile-page">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-slate-400">{ws.profile_label}</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">{ws.profile_title}</h1>
        <p className="text-sm text-slate-500">{ws.profile_subtitle}</p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="rounded-3xl bg-white/80 p-8 shadow-[0_20px_50px_rgba(15,23,42,0.08)] backdrop-blur"
        data-testid="profile-form"
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Full name</label>
            <Input
              value={form.full_name}
              onChange={(e) => handleChange("full_name", e.target.value)}
              data-testid="profile-name-input"
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Company</label>
            <Input
              value={form.company_name}
              onChange={(e) => handleChange("company_name", e.target.value)}
              data-testid="profile-company-input"
              required={companyRequired}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <label className="text-sm text-slate-600">Email address</label>
              <Lock size={11} className="text-slate-400" />
            </div>
            <Input
              value={user?.email || ""}
              readOnly
              className="bg-slate-50 cursor-not-allowed text-slate-500"
              data-testid="profile-email-input"
            />
            <p className="text-xs text-slate-400">Email can only be changed by an admin from the admin panel.</p>
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Partner / Tenant Code</label>
            <div className="flex items-center gap-2">
              <Input
                value={user?.partner_code || "—"}
                readOnly
                className="bg-slate-50 cursor-not-allowed font-mono text-sm"
                data-testid="profile-partner-code"
              />
              <span className="text-xs text-slate-400 whitespace-nowrap">Read-only</span>
            </div>
            <p className="text-xs text-slate-400">Use this code when logging in via the partner portal.</p>
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Phone{phoneRequired && <span className="text-red-500 ml-0.5">*</span>}</label>
            <Input
              value={form.phone}
              onChange={(e) => { handleChange("phone", e.target.value); setPhoneError(validatePhone(e.target.value)); }}
              onBlur={e => setPhoneError(validatePhone(e.target.value))}
              data-testid="profile-phone-input"
              required={phoneRequired}
              type="tel"
              placeholder="+1 (555) 000-0000"
            />
            {phoneError && <p className="text-xs text-red-500">{phoneError}</p>}
          </div>
          {isAdmin && tenantCountry && (
            <div className="space-y-2">
              <label className="text-sm text-slate-600">Business Country (from Tax Settings)</label>
              <div className="flex items-center gap-2">
                <Input
                  value={tenantCountry}
                  readOnly
                  className="bg-slate-50 cursor-not-allowed font-mono text-sm"
                  data-testid="profile-admin-country"
                />
                <span className="text-xs text-slate-400 whitespace-nowrap">Read-only</span>
              </div>
              <p className="text-xs text-slate-400">Set via Admin &rsaquo; Taxes &rsaquo; Tax Settings.</p>
            </div>
          )}
          <div className="space-y-2 md:col-span-2">
            <label className="text-sm text-slate-600">Address line 1</label>
            <Input
              value={form.line1}
              onChange={(e) => handleChange("line1", e.target.value)}
              data-testid="profile-line1-input"
              required
            />
          </div>
          <div className="space-y-2 md:col-span-2">
            <label className="text-sm text-slate-600">Address line 2</label>
            <Input
              value={form.line2}
              onChange={(e) => handleChange("line2", e.target.value)}
              data-testid="profile-line2-input"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">City</label>
            <Input
              value={form.city}
              onChange={(e) => handleChange("city", e.target.value)}
              data-testid="profile-city-input"
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">State / Province</label>
            {provinces.length > 0 ? (
              <Select value={form.region} onValueChange={(v) => handleChange("region", v)}>
                <SelectTrigger data-testid="profile-region-select">
                  <SelectValue placeholder="Select province / state" />
                </SelectTrigger>
                <SelectContent>
                  {provinces.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                </SelectContent>
              </Select>
            ) : (
              <Input
                value={form.region}
                onChange={(e) => handleChange("region", e.target.value)}
                data-testid="profile-region-input"
                required
              />
            )}
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Postal / ZIP</label>
            <Input
              value={form.postal}
              onChange={(e) => handleChange("postal", e.target.value)}
              data-testid="profile-postal-input"
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Country (locked)</label>
            <Input
              value={form.country}
              readOnly
              disabled
              className="bg-slate-50 cursor-not-allowed"
              data-testid="profile-country-input"
            />
          </div>
        </div>
        <div className="mt-6 flex items-center justify-end">
          <Button
            type="submit"
            className="rounded-full bg-slate-900 text-white hover:bg-slate-800"
            disabled={loading}
            data-testid="profile-save-button"
          >
            {loading ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </form>

      {/* GDPR Data Privacy Section - Hidden in Advanced Settings */}
      <details className="mt-8 border-t border-slate-200 pt-6 group">
        <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-600 transition-colors list-none flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider">Advanced Settings</span>
          <svg className="w-3 h-3 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </summary>
        
        <div className="mt-4">
          <details className="group/gdpr">
            <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-600 transition-colors list-none flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-wider">Data Privacy (GDPR)</span>
              <svg className="w-3 h-3 transition-transform group-open/gdpr:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </summary>
            
            <div className="mt-4 space-y-4">
              <p className="text-xs text-slate-500">
                Manage your personal data. You can export all your data or request account deletion.
              </p>

              {/* Export Data */}
              <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-200">
                <div>
                  <p className="text-sm font-medium text-slate-700">Export my data</p>
                  <p className="text-xs text-slate-500">Download all your personal data in a ZIP file</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleExportData}
                  disabled={exporting}
                  data-testid="gdpr-export-btn"
                >
                  <Download className="w-4 h-4 mr-2" />
                  {exporting ? "Exporting..." : "Export Data"}
                </Button>
              </div>

              {/* Delete Account */}
              <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-red-700">Delete my account</p>
                    <p className="text-xs text-red-600">Permanently anonymize all your data. This cannot be undone.</p>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => setShowDeleteConfirm(true)}
                    data-testid="gdpr-delete-btn"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete Account
                  </Button>
                </div>

                {showDeleteConfirm && (
                  <div className="mt-4 p-4 bg-white rounded-lg border border-red-300">
                    <div className="flex items-start gap-3 mb-3">
                      <AlertTriangle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-red-700">Are you sure?</p>
                        <p className="text-xs text-red-600 mt-1">
                          This will permanently anonymize your account and all associated data. 
                          You will be logged out and cannot recover your account.
                        </p>
                      </div>
                    </div>
                    <div className="mb-3">
                      <label className="text-xs font-medium text-slate-600">Reason (optional)</label>
                      <Input
                        value={deleteReason}
                        onChange={(e) => setDeleteReason(e.target.value)}
                        placeholder="Why are you leaving?"
                        className="mt-1"
                        data-testid="gdpr-delete-reason"
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={handleDeleteAccount}
                        disabled={deleting}
                        data-testid="gdpr-delete-confirm-btn"
                      >
                        {deleting ? "Deleting..." : "Yes, delete my account"}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowDeleteConfirm(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </details>
        </div>
      </details>
    </div>
  );
}
