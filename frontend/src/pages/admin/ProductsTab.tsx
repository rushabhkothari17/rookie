import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ImportModal } from "@/components/admin/ImportModal";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHeader, TableRow } from "@/components/ui/table";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { CategoriesTab } from "./CategoriesTab";
import { PromoCodesTab } from "./PromoCodesTab";
import { TermsTab } from "./TermsTab";
import { Download, Upload, ExternalLink, Package, FolderTree, Tag, FileText } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { ColHeader } from "@/components/shared/ColHeader";
import { useSupportedCurrencies } from "@/hooks/useSupportedCurrencies";

export function ProductsTab() {
  const { user: authUser } = useAuth();
  const isPlatformAdmin = authUser?.role === "platform_admin";
  const { currencies: supportedCurrencies } = useSupportedCurrencies();
  const [activeSubTab, setActiveSubTab] = useState("products");
  const navigate = useNavigate();
  const [showImport, setShowImport] = useState(false);
  const [products, setProducts] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string[]>([]);
  const [billingFilter, setBillingFilter] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [nameFilter, setNameFilter] = useState<string[]>([]);
  const [priceRange, setPriceRange] = useState<{ min?: string; max?: string; currency?: string }>({});
  const [page, setPage] = useState(1);
  const [logsUrl, setLogsUrl] = useState("");
  const [showAuditLogs, setShowAuditLogs] = useState(false);
  const [confirmToggleProduct, setConfirmToggleProduct] = useState<any>(null);
  const PER_PAGE = 20;

  const load = async () => {
    setLoading(true);
    try {
      const [prodRes, catRes] = await Promise.all([
        api.get("/admin/products-all?per_page=500"),
        api.get("/admin/categories?per_page=500").catch(() => ({ data: { categories: [] } })),
      ]);
      setProducts(
        (prodRes.data.products || []).sort((a: any, b: any) =>
          (a.name || "").localeCompare(b.name || "")
        )
      );
      setCategories(catRes.data.categories || []);
    } catch {
      toast.error("Failed to load products");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => navigate("/admin/products/new");
  const openEdit = (p: any) => navigate(`/admin/products/${p.id}/edit`);

  const handleToggleActive = async (p: any) => {
    try {
      await api.put(`/admin/products/${p.id}`, { name: p.name, is_active: !p.is_active });
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
      const res = await fetch(`${baseUrl}/api/admin/export/catalog`, { headers: { Authorization: `Bearer ${token}` } });
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

  const [colSort, setColSort] = useState<{ col: string; dir: "asc" | "desc" } | null>(null);

  // Build unique options for dropdowns
  const uniqueNames = useMemo(() => {
    return Array.from(new Set(products.map(p => p.name).filter(Boolean))).sort().map(n => [n, n] as [string, string]);
  }, [products]);

  const uniqueCategories = useMemo(() => {
    return categories.map((c: any) => [c.name, c.name] as [string, string]);
  }, [categories]);

  const filtered = products.filter((p) => {
    // Name filter (multi-select)
    const matchName = nameFilter.length === 0 || nameFilter.some(n => p.name === n);
    // Category filter (multi-select)
    const matchCategory = categoryFilter.length === 0 || categoryFilter.includes(p.category);
    // Billing filter (multi-select)
    const matchBilling = billingFilter.length === 0 || billingFilter.some(f => {
      if (f === "subscription") return p.is_subscription;
      if (f === "one-time") return !p.is_subscription;
      return true;
    });
    // Status filter (multi-select)
    const matchStatus = statusFilter.length === 0 || statusFilter.some(s => {
      if (s === "active") return p.is_active;
      if (s === "inactive") return !p.is_active;
      return true;
    });
    // Price range filter
    const matchPrice = (!priceRange.currency || (p.currency || "USD") === priceRange.currency) &&
                       (!priceRange.min || (p.base_price && p.base_price >= parseFloat(priceRange.min))) &&
                       (!priceRange.max || (p.base_price && p.base_price <= parseFloat(priceRange.max)));
    return matchName && matchCategory && matchBilling && matchStatus && matchPrice;
  });

  const displayFiltered = useMemo(() => {
    const r = [...filtered];
    if (colSort) {
      r.sort((a, b) => {
        let av: any = "", bv: any = "";
        if (colSort.col === "name") { av = a.name?.toLowerCase() || ""; bv = b.name?.toLowerCase() || ""; }
        else if (colSort.col === "category") { av = a.category || ""; bv = b.category || ""; }
        else if (colSort.col === "billing") { av = a.is_subscription ? 1 : 0; bv = b.is_subscription ? 1 : 0; }
        else if (colSort.col === "price") { av = a.base_price || 0; bv = b.base_price || 0; }
        else if (colSort.col === "status") { av = a.is_active ? 1 : 0; bv = b.is_active ? 1 : 0; }
        if (av < bv) return colSort.dir === "asc" ? -1 : 1;
        if (av > bv) return colSort.dir === "asc" ? 1 : -1;
        return 0;
      });
    }
    return r;
  }, [filtered, colSort]);

  const paged = displayFiltered.slice((page - 1) * PER_PAGE, page * PER_PAGE);
  const totalPages = Math.max(1, Math.ceil(displayFiltered.length / PER_PAGE));

  return (
    <div className="space-y-4">
      <Tabs value={activeSubTab} onValueChange={setActiveSubTab} className="w-full">
        <TabsList className="bg-slate-100 p-1 rounded-lg w-fit flex-wrap">
          <TabsTrigger value="products" className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-md px-4 py-2 text-sm font-medium gap-2" data-testid="products-subtab-products">
            <Package size={16} />
            Products
          </TabsTrigger>
          <TabsTrigger value="categories" className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-md px-4 py-2 text-sm font-medium gap-2" data-testid="products-subtab-categories">
            <FolderTree size={16} />
            Categories
          </TabsTrigger>
          <TabsTrigger value="promo" className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-md px-4 py-2 text-sm font-medium gap-2" data-testid="products-subtab-promo">
            <Tag size={16} />
            Promo Codes
          </TabsTrigger>
          <TabsTrigger value="terms" className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-md px-4 py-2 text-sm font-medium gap-2" data-testid="products-subtab-terms">
            <FileText size={16} />
            Terms
          </TabsTrigger>
        </TabsList>

        <TabsContent value="products" className="mt-4">
          <div className="space-y-4">
            <AdminPageHeader title="Products" subtitle={`${filtered.length} products`} actions={
              <>
                <Button variant="outline" size="sm" onClick={downloadCsv} data-testid="admin-catalog-export-csv"><Download size={14} className="mr-1" />Export CSV</Button>
                <Button variant="outline" size="sm" onClick={() => setShowImport(true)} data-testid="admin-catalog-import-csv"><Upload size={14} className="mr-1" />Import CSV</Button>
                <Button size="sm" onClick={openCreate} data-testid="admin-create-product-btn">+ New Product</Button>
              </>
            } />
            {/* Filters removed — use column headers */}
            <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
              <Table data-testid="admin-catalog-table">
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <ColHeader label="Name" colKey="name" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={nameFilter} onFilter={v => { setNameFilter(v); setPage(1); }} onClearFilter={() => { setNameFilter([]); setPage(1); }} statusOptions={uniqueNames} />
                    <ColHeader label="Category" colKey="category" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={categoryFilter} onFilter={v => { setCategoryFilter(v); setPage(1); }} onClearFilter={() => { setCategoryFilter([]); setPage(1); }} statusOptions={uniqueCategories} />
                    <ColHeader label="Billing" colKey="billing" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={billingFilter} onFilter={v => { setBillingFilter(v); setPage(1); }} onClearFilter={() => { setBillingFilter([]); setPage(1); }} statusOptions={[["subscription", "Subscription"], ["one-time", "One-time"]]} />
                    <ColHeader label="Price" colKey="price" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="number-range" filterValue={priceRange} onFilter={v => { setPriceRange(v); setPage(1); }} onClearFilter={() => { setPriceRange({}); setPage(1); }} currencyOptions={supportedCurrencies.map(c => [c, c] as [string, string])} />
                    <ColHeader label="Status" colKey="status" sortCol={colSort?.col} sortDir={colSort?.dir} onSort={(c, d) => setColSort({ col: c, dir: d })} onClearSort={() => setColSort(null)} filterType="dropdown" filterValue={statusFilter} onFilter={v => { setStatusFilter(v); setPage(1); }} onClearFilter={() => { setStatusFilter([]); setPage(1); }} statusOptions={[["active", "Active"], ["inactive", "Inactive"]]} />
                    {isPlatformAdmin && <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Partner</th>}
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">Actions</th>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading && <TableRow><TableCell colSpan={isPlatformAdmin ? 7 : 6} className="text-center text-slate-400">Loading...</TableCell></TableRow>}
                  {!loading && displayFiltered.length === 0 && <TableRow><TableCell colSpan={isPlatformAdmin ? 7 : 6} className="text-center text-slate-400">No products found.</TableCell></TableRow>}
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
                      <TableCell className="text-sm">{product.base_price ? new Intl.NumberFormat("en-US", { style: "currency", currency: product.currency || "USD", minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(product.base_price) : product.pricing_type === "enquiry" ? <span className="text-slate-400 text-xs">RFQ</span> : <span className="text-slate-400 text-xs">{new Intl.NumberFormat("en-US", { style: "currency", currency: product.currency || "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(0)}</span>}</TableCell>
                      <TableCell>
                        <span className={`text-xs px-2 py-0.5 rounded font-medium ${product.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                          {product.is_active ? "Active" : "Inactive"}
                        </span>
                      </TableCell>
                      {isPlatformAdmin && <TableCell className="text-xs text-slate-500" data-testid={`admin-product-partner-${product.id}`}>{product.partner_code || "—"}</TableCell>}
                      <TableCell>
                        <div className="flex gap-2 items-center">
                          <Button variant="outline" size="sm" onClick={() => openEdit(product)} className="gap-1" data-testid={`admin-edit-${product.id}`}>
                            <ExternalLink size={14} />Edit
                          </Button>
                          <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => { setLogsUrl(`/admin/products/${product.id}/logs`); setShowAuditLogs(true); }} data-testid={`admin-product-logs-${product.id}`}>Logs</Button>
                          <Button variant={product.is_active ? "destructive" : "outline"} size="sm" onClick={() => setConfirmToggleProduct(product)} data-testid={`admin-toggle-${product.id}`}>
                            {product.is_active ? "Deactivate" : "Activate"}
                          </Button>
                          <a href={`/product/${product.id}`} target="_blank" rel="noreferrer" className="text-xs text-slate-400 hover:text-slate-700 underline" data-testid={`admin-preview-${product.id}`}>Preview</a>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <AdminPagination page={page} totalPages={totalPages} total={displayFiltered.length} perPage={PER_PAGE} onPage={(p) => setPage(p)} />
            <AuditLogDialog open={showAuditLogs} onOpenChange={setShowAuditLogs} title="Product Audit Logs" logsUrl={logsUrl} />
            <ImportModal entity="catalog" entityLabel="Products" open={showImport} onClose={() => setShowImport(false)} onSuccess={load} />
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
                  <AlertDialogAction className={confirmToggleProduct?.is_active ? "bg-red-600 hover:bg-red-700" : ""} onClick={() => { handleToggleActive(confirmToggleProduct); setConfirmToggleProduct(null); }} data-testid="confirm-product-toggle">
                    {confirmToggleProduct?.is_active ? "Deactivate" : "Activate"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </TabsContent>

        <TabsContent value="categories" className="mt-4">
          <CategoriesTab />
        </TabsContent>

        <TabsContent value="promo" className="mt-4">
          <PromoCodesTab />
        </TabsContent>

        <TabsContent value="terms" className="mt-4">
          <TermsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
