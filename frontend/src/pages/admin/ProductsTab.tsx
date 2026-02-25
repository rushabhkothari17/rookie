import { useEffect, useState } from "react";
import { ImportModal } from "@/components/admin/ImportModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { ProductForm, ProductFormData, EMPTY_FORM } from "./ProductForm";
import { EMPTY_INTAKE_SCHEMA } from "./IntakeSchemaBuilder";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { Download, Upload} from "lucide-react";

function productToForm(p: any): ProductFormData {
  // bullets: prefer new 'bullets' field, fall back to bullets_included
  const bullets: string[] = (p.bullets || []).filter((b: string) => b);
  if (bullets.length === 0) {
    const fallback = (p.bullets_included || []).filter((b: string) => b);
    if (fallback.length > 0) bullets.push(...fallback);
    else bullets.push("");
  }

  return {
    name: p.name || "",
    short_description: p.short_description || p.tagline || "",
    description_long: p.description_long || "",
    bullets,
    tag: p.tag || "",
    category: p.category || "",
    faqs: Array.isArray(p.faqs)
      ? p.faqs.map((f: any) => typeof f === "string" ? { question: f, answer: "" } : f)
      : [],
    terms_id: p.terms_id || "",
    base_price: p.base_price ?? 0,
    is_subscription: p.is_subscription ?? false,
    stripe_price_id: p.stripe_price_id || "",
    price_rounding: p.price_rounding || "",
    is_active: p.is_active ?? true,
    visible_to_customers: p.visible_to_customers || [],
    restricted_to: p.restricted_to || [],
    intake_schema_json: p.intake_schema_json || EMPTY_INTAKE_SCHEMA,
    custom_sections: p.custom_sections || [],
    pricing_rules: p.pricing_rules || {},
  };
}

export function ProductsTab() {
  const [showImport, setShowImport] = useState(false);
  const [products, setProducts] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [terms, setTerms] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [catalogFilter, setCatalogFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [searchText, setSearchText] = useState("");
  const [showDialog, setShowDialog] = useState(false);
  const [editProduct, setEditProduct] = useState<any>(null);
  const [form, setForm] = useState<ProductFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(1);
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const [confirmToggleProduct, setConfirmToggleProduct] = useState<any>(null);
  const PER_PAGE = 20;

  const load = async () => {
    setLoading(true);
    try {
      const [prodRes, catRes, custRes, termsRes] = await Promise.all([
        api.get("/admin/products-all?per_page=500"),
        api.get("/admin/categories?per_page=500").catch(() => ({ data: { categories: [] } })),
        api.get("/admin/customers?per_page=1000").catch(() => ({ data: { customers: [], users: [] } })),
        api.get("/admin/terms").catch(() => ({ data: { terms: [] } })),
      ]);
      setProducts(
        (prodRes.data.products || []).sort((a: any, b: any) =>
          (a.name || "").localeCompare(b.name || "")
        )
      );
      setCategories(catRes.data.categories || []);
      // Merge user email into customers for typeahead
      const usersArr: any[] = custRes.data.users || [];
      const userEmailMap: Record<string, string> = {};
      usersArr.forEach((u: any) => { userEmailMap[u.id] = u.email || ""; });
      const enrichedCustomers = (custRes.data.customers || []).map((c: any) => ({
        ...c, email: userEmailMap[c.user_id] || "",
      }));
      setCustomers(enrichedCustomers);
      setTerms(termsRes.data.terms || []);
    } catch {
      toast.error("Failed to load products");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // Re-fetch categories whenever the dialog opens to pick up newly added categories
  useEffect(() => {
    if (showDialog) {
      api.get("/admin/categories?per_page=500")
        .then(res => setCategories(res.data.categories || []))
        .catch(() => {});
    }
  }, [showDialog]);

  const openCreate = () => {
    setEditProduct(null);
    setForm(EMPTY_FORM);
    setShowDialog(true);
  };

  const openEdit = (p: any) => {
    setEditProduct(p);
    setForm(productToForm(p));
    setShowDialog(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error("Product name is required"); return; }
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        short_description: form.short_description,
        description_long: form.description_long,
        bullets: form.bullets.filter(b => b.trim()),
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
        tagline: form.short_description,
        pricing_rules: form.pricing_rules || editProduct?.pricing_rules || {},
      };
      if (editProduct) {
        await api.put(`/admin/products/${editProduct.id}`, payload);
        toast.success("Product updated");
      } else {
        await api.post("/admin/products", payload);
        toast.success("Product created");
      }
      setShowDialog(false);
      load();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to save product");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (p: any) => {
    try {
      await api.put(`/admin/products/${p.id}`, {
        name: p.name,
        is_active: !p.is_active,
        pricing_rules: p.pricing_rules || {},
      });
      toast.success(`Product ${p.is_active ? "deactivated" : "activated"}`);
      load();
    } catch {
      toast.error("Failed to update product");
    }
  };

  const downloadCsv = async () => {
    try {
      const token = localStorage.getItem("aa_token");
      const baseUrl = process.env.REACT_APP_BACKEND_URL;
      const res = await fetch(`${baseUrl}/api/admin/export/catalog`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `catalog_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("CSV export failed");
    }
  };

  const filtered = products.filter((p) => {
    const matchFilter =
      catalogFilter === "all" ||
      (catalogFilter === "subscription" && p.is_subscription) ||
      (catalogFilter === "one-time" && !p.is_subscription) ||
      (catalogFilter === "active" && p.is_active) ||
      (catalogFilter === "inactive" && !p.is_active);
    const matchCategory = categoryFilter === "all" || p.category === categoryFilter;
    const matchSearch = !searchText || p.name?.toLowerCase().includes(searchText.toLowerCase()) || p.category?.toLowerCase().includes(searchText.toLowerCase());
    return matchFilter && matchCategory && matchSearch;
  });
  const paged = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));

  return (
    <div className="space-y-4">
      <AdminPageHeader title="Catalog" subtitle={`${filtered.length} products`} actions={
        <>
          <Button variant="outline" size="sm" onClick={downloadCsv} data-testid="admin-catalog-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
          <Button variant="outline" size="sm" onClick={() => setShowImport(true)} data-testid="admin-catalog-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
          <Button size="sm" onClick={openCreate} data-testid="admin-create-product-btn">+ New Product</Button>
        </>
      } />

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input placeholder="Search products…" value={searchText} onChange={(e) => setSearchText(e.target.value)} className="h-8 text-xs w-44" data-testid="admin-products-search" />
          <Select value={catalogFilter} onValueChange={v => { setCatalogFilter(v); setPage(1); }}>
            <SelectTrigger className="h-8 text-xs w-32" data-testid="admin-catalog-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Billing</SelectItem>
              <SelectItem value="subscription">Subscriptions</SelectItem>
              <SelectItem value="one-time">One-time</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="inactive">Inactive</SelectItem>
            </SelectContent>
          </Select>
          <Select value={categoryFilter} onValueChange={v => { setCategoryFilter(v); setPage(1); }}>
            <SelectTrigger className="h-8 text-xs w-40 bg-white" data-testid="admin-catalog-category-filter"><SelectValue placeholder="All Categories" /></SelectTrigger>
            <SelectContent><SelectItem value="all">All Categories</SelectItem>{categories.map((c: any) => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}</SelectContent>
          </Select>
          <Button size="sm" variant="outline" onClick={() => { setSearchText(""); setCatalogFilter("all"); setCategoryFilter("all"); setPage(1); }} className="h-8 text-xs" data-testid="admin-catalog-clear-filters">Clear</Button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <Table data-testid="admin-catalog-table">
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Name</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Billing</TableHead>
              <TableHead>Price</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={6} className="text-center text-slate-400">Loading…</TableCell></TableRow>
            )}
            {!loading && filtered.length === 0 && (
              <TableRow><TableCell colSpan={6} className="text-center text-slate-400">No products found.</TableCell></TableRow>
            )}
            {paged.map((product) => (
              <TableRow key={product.id} data-testid={`admin-product-row-${product.id}`}>
                <TableCell>
                  <div className="font-medium text-sm">{product.name}</div>
                  {product.tag && <span className="text-xs text-slate-400">{product.tag}</span>}
                </TableCell>
                <TableCell className="text-xs text-slate-500">{product.category}</TableCell>
                <TableCell>
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${product.is_subscription ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"}`}>
                    {product.is_subscription ? "Subscription" : "One-time"}
                  </span>
                </TableCell>
                <TableCell className="text-sm">{product.base_price ? `$${product.base_price}` : <span className="text-slate-400 text-xs">RFQ</span>}</TableCell>
                <TableCell>
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${product.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                    {product.is_active ? "Active" : "Inactive"}
                  </span>
                </TableCell>
                <TableCell>
                  <div className="flex gap-2 items-center">
                    <Button variant="outline" size="sm" onClick={() => openEdit(product)} data-testid={`admin-edit-${product.id}`}>Edit</Button>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setLogsUrl(`/admin/products/${product.id}/logs`); setShowAuditLogs(true); }} data-testid={`admin-product-logs-${product.id}`}>Logs</Button>
                    <Button
                      variant={product.is_active ? "destructive" : "outline"}
                      size="sm"
                      onClick={() => setConfirmToggleProduct(product)}
                      data-testid={`admin-toggle-${product.id}`}
                    >
                      {product.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    <a
                      href={`/product/${product.id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-slate-400 hover:text-slate-700 underline"
                      data-testid={`admin-preview-${product.id}`}
                    >
                      Preview
                    </a>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <AdminPagination page={page} totalPages={totalPages} total={filtered.length} perPage={PER_PAGE} onPage={(p) => setPage(p)} />

      {/* Product Create/Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={(open) => { if (!open) setShowDialog(false); }}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="admin-product-dialog">
          <DialogHeader>
            <DialogTitle>{editProduct ? `Edit: ${editProduct.name}` : "New Product"}</DialogTitle>
          </DialogHeader>
          <ProductForm
            form={form}
            setForm={setForm}
            categories={categories}
            customers={customers}
            terms={terms}
          />
          <div className="flex gap-2 justify-end pt-4 border-t border-slate-100 sticky bottom-0 bg-white pb-1">
            <Button variant="outline" onClick={() => setShowDialog(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving} data-testid="admin-product-save-btn">
              {saving ? "Saving…" : "Save Product"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AuditLogDialog open={showAuditLogs} onOpenChange={setShowAuditLogs} title="Product Audit Logs" logsUrl={logsUrl} />
      <ImportModal
        entity="catalog"
        entityLabel="Catalog"
        open={showImport}
        onClose={() => setShowImport(false)}
        onSuccess={load}
      />

      {/* Deactivate/Activate Product Confirmation */}
      <AlertDialog open={!!confirmToggleProduct} onOpenChange={(open) => !open && setConfirmToggleProduct(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmToggleProduct?.is_active ? "Deactivate Product" : "Activate Product"}</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to {confirmToggleProduct?.is_active ? "deactivate" : "activate"} "{confirmToggleProduct?.name}"?
              {confirmToggleProduct?.is_active && " It will no longer be visible in the store."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={confirmToggleProduct?.is_active ? "bg-red-600 hover:bg-red-700" : ""}
              onClick={() => { handleToggleActive(confirmToggleProduct); setConfirmToggleProduct(null); }}
              data-testid="confirm-product-toggle"
            >
              {confirmToggleProduct?.is_active ? "Deactivate" : "Activate"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
