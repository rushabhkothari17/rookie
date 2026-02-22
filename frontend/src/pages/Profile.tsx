import { useEffect, useState } from "react";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { useWebsite } from "@/contexts/WebsiteContext";
import api from "@/lib/api";

export default function Profile() {
  const { user, customer, address, refresh } = useAuth();
  const ws = useWebsite();
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
  }, [user, address]);

  const handleChange = (key: string, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
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
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Email (verified)</label>
            <Input value={user?.email || ""} readOnly data-testid="profile-email-input" />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">Phone</label>
            <Input
              value={form.phone}
              onChange={(e) => handleChange("phone", e.target.value)}
              data-testid="profile-phone-input"
              required
            />
          </div>
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
            <Input
              value={form.region}
              onChange={(e) => handleChange("region", e.target.value)}
              data-testid="profile-region-input"
              required
            />
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
        <div className="mt-6 flex items-center justify-between">
          <div className="text-xs text-slate-500" data-testid="profile-currency-note">
            Preferred currency: {customer?.currency || ""}
          </div>
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
    </div>
  );
}
