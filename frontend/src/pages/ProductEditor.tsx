/**
 * Full-screen Product Editor Page
 * Routes: /admin/products/new and /admin/products/:id/edit
 */
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { ArrowLeft, Save, Loader2 } from "lucide-react";
import api from "@/lib/api";
import { ProductForm, type ProductFormData, EMPTY_FORM } from "./admin/ProductForm";
import { EMPTY_INTAKE_SCHEMA } from "./admin/IntakeSchemaBuilder";

export default function ProductEditor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isNew = !id;
  
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [categories, setCategories] = useState<{ id: string; name: string }[]>([]);
  const [customers, setCustomers] = useState<{ id: string; name: string; email: string }[]>([]);
  const [terms, setTerms] = useState<{ id: string; title: string }[]>([]);
  
  const [form, setForm] = useState<ProductFormData>({
    name: "",
    tagline: "",
    card_title: "",
    card_tag: "",
    card_description: "",
    card_bullets: [],
    description_long: "",
    bullets: [],
    tag: "",
    category: "",
    faqs: [],
    terms_id: "",
    base_price: 0,
    is_subscription: false,
    stripe_price_id: "",
    price_rounding: "",
    pricing_type: "internal",
    external_url: "",
    currency: "USD",
    is_active: true,
    visible_to_customers: [],
    restricted_to: [],
    visibility_conditions: null,
    intake_schema_json: EMPTY_INTAKE_SCHEMA,
    custom_sections: [],
    display_layout: "standard",
  });

  useEffect(() => {
    const loadData = async () => {
      try {
        const [catRes, custRes, termsRes] = await Promise.all([
          api.get("/categories"),
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
      tagline: p.tagline || "",
      card_title: p.card_title || "",
      card_tag: p.card_tag || "",
      card_description: p.card_description || "",
      card_bullets: p.card_bullets || [],
      description_long: p.description_long || "",
      bullets,
      tag: p.tag || "",
      category: p.category || "",
      faqs: Array.isArray(p.faqs)
        ? p.faqs.map((f: any) => (typeof f === "string" ? { question: f, answer: "" } : f))
        : [],
      terms_id: p.terms_id || "",
      base_price: p.base_price ?? 0,
      is_subscription: p.is_subscription ?? false,
      stripe_price_id: p.stripe_price_id || "",
      price_rounding: p.price_rounding || "",
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
        tagline: form.tagline,
        card_title: form.card_title || null,
        card_tag: form.card_tag || null,
        card_description: form.card_description || null,
        card_bullets: form.card_bullets.length > 0 ? form.card_bullets : null,
        description_long: form.description_long,
        bullets: form.bullets.filter((b) => b.trim()),
        tag: form.tag || null,
        category: form.category,
        faqs: form.faqs,
        terms_id: form.terms_id || null,
        base_price: form.base_price,
        is_subscription: form.is_subscription,
        stripe_price_id: form.stripe_price_id || null,
        price_rounding: form.price_rounding || null,
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
        />
      </div>
    </div>
  );
}
