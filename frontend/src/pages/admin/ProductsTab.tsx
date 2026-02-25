import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ImportModal } from "@/components/admin/ImportModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import api from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { AdminPageHeader } from "./shared/AdminPageHeader";
import { AdminPagination } from "./shared/AdminPagination";
import { AuditLogDialog } from "@/components/AuditLogDialog";
import { CategoriesTab } from "./CategoriesTab";
import { Download, Upload, ExternalLink, Package, FolderTree } from "lucide-react";

export function ProductsTab() {
  const [activeSubTab, setActiveSubTab] = useState("products");
  const navigate = useNavigate();
  const [showImport, setShowImport] = useState(false);
  const [products, setProducts] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [catalogFilter, setCatalogFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [searchText, setSearchText] = useState("");
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
      <Tabs value={activeSubTab} onValueChange={setActiveSubTab} className="w-full">
        <TabsList className="bg-slate-100 p-1 rounded-lg w-fit">
          <TabsTrigger value="products" className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-md px-4 py-2 text-sm font-medium gap-2" data-testid="products-subtab-products">
            <Package size={16} />
            Products
          </TabsTrigger>
          <TabsTrigger value="categories" className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-md px-4 py-2 text-sm font-medium gap-2" data-testid="products-subtab-categories">
            <FolderTree size={16} />
            Categories
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
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Input placeholder="Search products..." value={searchText} onChange={(e) => setSearchText(e.target.value)} className="h-8 text-xs w-44" data-testid="admin-products-search" />
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
                  {loading && <TableRow><TableCell colSpan={6} className="text-center text-slate-400">Loading...</TableCell></TableRow>}
                  {!loading && filtered.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-slate-400">No products found.</TableCell></TableRow>}
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
            <AdminPagination page={page} totalPages={totalPages} total={filtered.length} perPage={PER_PAGE} onPage={(p) => setPage(p)} />
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
      </Tabs>
    </div>
  );
}
