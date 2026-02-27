/**
 * Full-screen Product Editor Page
 * Routes: /admin/products/new and /admin/products/:id/edit
 */
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { ArrowLeft, Save, Loader2, Eye, X as XIcon, Store } from "lucide-react";
import api from "@/lib/api";
import { ProductForm, type ProductFormData, EMPTY_FORM } from "./admin/ProductForm";
import { EMPTY_INTAKE_SCHEMA } from "./admin/IntakeSchemaBuilder";
import OfferingCard from "@/components/OfferingCard";

export default function ProductEditor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isNew = !id;
  
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [categories, setCategories] = useState<{ id: string; name: string }[]>([]);
  const [customers, setCustomers] = useState<{ id: string; name: string; email: string }[]>([]);
  const [terms, setTerms] = useState<{ id: string; title: string }[]>([]);
  
  const [form, setForm] = useState<ProductFormData>({
    ...EMPTY_FORM,
    intake_schema_json: EMPTY_INTAKE_SCHEMA,
  });

  useEffect(() => {
    const loadData = async () => {
      try {
        const [catRes, custRes, termsRes] = await Promise.all([
          api.get("/admin/categories"),
          api.get("/admin/customers?per_page=500"),
          api.get("/admin/terms"),
        ]);
        setCategories(catRes.data.categories || []);
        // Enrich customers with email (from users) and address data for client-side preview
        const rawCustomers = custRes.data.customers || [];
        const users: any[] = custRes.data.users || [];
        const addresses: any[] = custRes.data.addresses || [];
        const enriched = rawCustomers.map((c: any) => {
          const user = users.find((u: any) => u.id === c.user_id);
          const addr = addresses.find((a: any) => a.customer_id === c.id);
          return { ...c, email: user?.email ?? "", full_name: user?.full_name ?? "", status: user?.is_active ? "active" : "inactive", country: addr?.country ?? "", state_province: addr?.region ?? "", phone: user?.phone ?? "" };
        });
        setCustomers(enriched);
        setTerms(termsRes.data.terms || []);

        if (id) {
          const prodRes = await api.get("/admin/products-all?per_page=500");
          const product = prodRes.data.products?.find((p: any) => p.id === id);
          if (product) {
            setForm(productToForm(product));
          } else {
            toast.error("Product not found");
            navigate("/admin?tab=catalog");
          }
        }
      } catch (err) {
        toast.error("Failed to load data");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [id, navigate]);

  const productToForm = (p: any): ProductFormData => {
    const bullets = Array.isArray(p.bullets) ? p.bullets : [];
    const legacyMap: Record<string, string> = {
      scope_request: "enquiry",
      inquiry: "enquiry",
    };
    const pricing_type = legacyMap[p.pricing_type] ?? p.pricing_type ?? "internal";
    const external_url = p.external_url || p.pricing_rules?.external_url || "";

    return {
      name: p.name || "",
      card_tag: p.card_tag || "",
      card_description: p.card_description || "",
      card_bullets: p.card_bullets || [],
      description_long: p.description_long || "",
      bullets,
      category: p.category || "",
      faqs: Array.isArray(p.faqs)
        ? p.faqs.map((f: any) => (typeof f === "string" ? { question: f, answer: "" } : f))
        : [],
      terms_id: p.terms_id || "",
      base_price: p.base_price ?? 0,
      is_subscription: p.is_subscription ?? false,
      stripe_price_id: p.stripe_price_id || "",
      price_rounding: p.price_rounding || "",
      show_price_breakdown: p.show_price_breakdown ?? false,
      pricing_type,
      external_url,
      is_active: p.is_active ?? true,
      visible_to_customers: p.visible_to_customers || [],
      restricted_to: p.restricted_to || [],
      visibility_conditions: p.visibility_conditions || null,
      intake_schema_json: p.intake_schema_json || EMPTY_INTAKE_SCHEMA,
      custom_sections: p.custom_sections || [],
      display_layout: p.display_layout || "standard",
      currency: p.currency || "USD",
      enquiry_form_id: p.enquiry_form_id || "",
    };
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error("Product name is required");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        card_tag: form.card_tag || null,
        card_description: form.card_description || null,
        card_bullets: form.card_bullets.filter((b) => b.trim()),
        description_long: form.description_long,
        bullets: form.bullets.filter((b) => b.trim()),
        category: form.category,
        faqs: form.faqs,
        terms_id: form.terms_id || null,
        base_price: form.base_price,
        is_subscription: form.is_subscription,
        stripe_price_id: form.stripe_price_id || null,
        price_rounding: form.price_rounding || null,
        show_price_breakdown: form.show_price_breakdown ?? false,
        is_active: form.is_active,
        visible_to_customers: form.visible_to_customers,
        restricted_to: form.restricted_to,
        intake_schema_json: form.intake_schema_json,
        custom_sections: form.custom_sections,
        pricing_type: form.pricing_type || "internal",
        external_url: form.external_url || null,
        display_layout: form.display_layout || "standard",
        currency: form.currency || "USD",
        visibility_conditions: form.visibility_conditions || null,
        enquiry_form_id: form.enquiry_form_id || null,
      };

      if (isNew) {
        await api.post("/admin/products", payload);
        toast.success("Product created");
      } else {
        await api.put(`/admin/products/${id}`, payload);
        toast.success("Product updated");
      }
      navigate("/admin?tab=catalog");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to save product");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50" data-testid="product-editor-page">
      {/* Header */}
      <div className="sticky top-0 z-50 bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/admin?tab=catalog")}
              className="gap-2"
              data-testid="product-editor-back"
            >
              <ArrowLeft size={16} />
              Back to Products
            </Button>
            <div className="h-6 w-px bg-slate-200" />
            <h1 className="text-lg font-semibold text-slate-900">
              {isNew ? "New Product" : form.name || "Edit Product"}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={() => setPreviewOpen(true)}
              className="gap-2"
              data-testid="product-editor-preview"
            >
              <Eye size={16} />
              Preview card
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate("/admin?tab=catalog")}
              data-testid="product-editor-cancel"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={saving}
              className="gap-2 bg-blue-600 hover:bg-blue-700"
              data-testid="product-editor-save"
            >
              {saving ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save size={16} />
                  {isNew ? "Create Product" : "Save Changes"}
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Form Content */}
      <div className="max-w-6xl mx-auto px-6 py-8">
        <ProductForm
          form={form}
          setForm={setForm}
          categories={categories}
          customers={customers}
          terms={terms}
          onSave={handleSave}
        />
      </div>

      {/* Store Card Preview Modal */}
      {previewOpen && (
        <StoreCardPreview form={form} onClose={() => setPreviewOpen(false)} />
      )}
    </div>
  );
}

/** Floating preview panel showing the store card as it will appear on the storefront */
function StoreCardPreview({ form, onClose }: { form: ProductFormData; onClose: () => void }) {
  const previewProduct = {
    id: "preview",
    name: form.name || "Untitled product",
    card_tag: form.card_tag || null,
    card_description: form.card_description || null,
    card_bullets: (form.card_bullets || []).filter((b) => b.trim()),
    category: form.category || "",
    base_price: Number(form.base_price) || 0,
    pricing_type: form.pricing_type || "internal",
    is_subscription: form.is_subscription,
    external_url: form.external_url || "",
    intake_schema_json: form.intake_schema_json,
    price_rounding: form.price_rounding || null,
    currency: form.currency || "GBP",
  };

  const hasCardContent = form.card_description || (form.card_bullets || []).filter(b => b.trim()).length > 0;
  const hasGeneralContent = (form.bullets || []).filter(b => b.trim()).length > 0 || form.description_long;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      data-testid="store-card-preview-modal"
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="relative z-10 bg-white rounded-2xl shadow-2xl max-w-2xl w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-2.5">
            <Store size={16} className="text-slate-500" />
            <span className="font-semibold text-slate-800 text-sm">Store card preview</span>
            <span className="text-[10px] text-slate-400 bg-slate-200 px-2 py-0.5 rounded-full uppercase tracking-wide">live preview</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 transition-colors"
            data-testid="store-card-preview-close"
          >
            <XIcon size={18} />
          </button>
        </div>

        {/* Preview area */}
        <div className="p-8 bg-slate-50">
          {/* Simulated store grid context */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg mx-auto">
            {/* The actual card */}
            <div className="sm:col-span-1">
              <OfferingCard product={previewProduct} />
            </div>
            {/* Ghost card to show grid context */}
            <div className="hidden sm:block rounded-2xl border border-dashed border-slate-200 bg-white/60 h-[220px]" />
          </div>
        </div>

        {/* Tips */}
        <div className="px-6 py-4 border-t border-slate-100 bg-white">
          <p className="text-[11px] text-slate-400 font-medium mb-2 uppercase tracking-wider">What's shown on the card</p>
          <div className="flex flex-wrap gap-2">
            <Chip active={!!form.name} label="Product name" />
            <Chip active={!!form.card_tag} label="Card tag" />
            <Chip active={!!form.card_description} label="Card description" />
            <Chip active={(form.card_bullets || []).filter(b => b.trim()).length > 0} label="Bullets" />
            <Chip active={(form.base_price ?? 0) > 0 || form.pricing_type === "enquiry"} label="Price / CTA" />
          </div>
          {!hasCardContent && (
            <p className="mt-3 text-[11px] text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              The "Store card" tab is empty. Add a card description or bullets to make this card more compelling.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Chip({ active, label }: { active: boolean; label: string }) {
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${
      active
        ? "bg-green-50 border-green-200 text-green-700"
        : "bg-slate-50 border-slate-200 text-slate-400"
    }`}>
      {active ? "✓" : "○"} {label}
    </span>
  );
}
