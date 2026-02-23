import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";
import { Copy, RefreshCw, Trash2, Eye, EyeOff, ChevronDown, ChevronRight, Play, Key, BookOpen, ExternalLink } from "lucide-react";
import api from "@/lib/api";

// ── API Endpoint Definitions ─────────────────────────────────────────────────

interface Param { name: string; in: "query" | "path" | "header" | "body"; type: string; required?: boolean; description: string; example?: string; }
interface EndpointDef { method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH"; path: string; summary: string; description: string; auth: "none" | "api-key" | "bearer"; tags: string[]; params?: Param[]; bodySchema?: Record<string, any>; responseExample?: Record<string, any>; }

const API_ENDPOINTS: EndpointDef[] = [
  // ── Tenant ───────────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/tenant-info", summary: "Verify API Key / Get tenant info",
    description: "Returns the tenant's display name. Use this to verify your API key is valid.",
    auth: "api-key", tags: ["Authentication"],
    responseExample: { tenant_id: "your-tenant-id", name: "Your Company Ltd", code: "your-code" },
  },
  // ── Auth ─────────────────────────────────────────────────────────────────
  {
    method: "POST", path: "/api/auth/customer-login", summary: "Login as customer",
    description: "Authenticate a customer and receive a JWT bearer token for subsequent requests.",
    auth: "api-key", tags: ["Authentication"],
    params: [],
    bodySchema: { email: "string", password: "string" },
    responseExample: { token: "eyJhbGci...", role: "customer", tenant_id: "your-tenant-id" },
  },
  {
    method: "POST", path: "/api/auth/register", summary: "Register a new customer",
    description: "Register a new customer account. Sends a verification email.",
    auth: "api-key", tags: ["Authentication"],
    bodySchema: { email: "string", password: "string", full_name: "string", company_name: "string (optional)" },
    responseExample: { success: true, message: "Verification email sent" },
  },
  // ── Catalog ──────────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/categories", summary: "List product categories",
    description: "Returns all active product categories with blurbs.",
    auth: "api-key", tags: ["Catalog"],
    params: [],
    responseExample: { categories: ["Bookkeeping", "Tax Returns"], category_blurbs: { "Bookkeeping": "Monthly bookkeeping services" } },
  },
  {
    method: "GET", path: "/api/products", summary: "List all products",
    description: "Returns all active, visible products. Respects customer visibility restrictions when authenticated.",
    auth: "api-key", tags: ["Catalog"],
    params: [],
    responseExample: { products: [{ id: "prod_xxx", name: "Starter Package", base_price: 499, billing_period: "monthly" }] },
  },
  {
    method: "GET", path: "/api/products/{id}", summary: "Get product details",
    description: "Returns full details for a single product including pricing schema.",
    auth: "api-key", tags: ["Catalog"],
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Product ID", example: "prod_abc123" }],
    responseExample: { product: { id: "prod_xxx", name: "Starter Package", pricing_type: "dynamic", intake_schema_json: [] } },
  },
  {
    method: "POST", path: "/api/pricing/calc", summary: "Calculate dynamic pricing",
    description: "Calculate the price for a product given customer-specific inputs. Use the product's intake_schema_json to know what inputs are required.",
    auth: "bearer", tags: ["Catalog"],
    bodySchema: { product_id: "string", inputs: { field_name: "value" } },
    responseExample: { product_id: "prod_xxx", total: 699, line_items: [] },
  },
  // ── Terms ─────────────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/terms", summary: "List terms & conditions",
    description: "Returns all terms & conditions documents for the tenant.",
    auth: "api-key", tags: ["Terms & Conditions"],
    responseExample: { terms: [{ id: "terms_xxx", title: "Standard Agreement", version: "1.0" }] },
  },
  {
    method: "GET", path: "/api/terms/{id}", summary: "Get T&C by ID",
    description: "Returns the full content of a specific terms & conditions document.",
    auth: "api-key", tags: ["Terms & Conditions"],
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Terms document ID", example: "terms_abc123" }],
    responseExample: { terms: { id: "terms_xxx", title: "Standard Agreement", content: "<h1>Terms</h1>..." } },
  },
  // ── Articles ──────────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/articles/public", summary: "List published articles",
    description: "Returns all published, publicly-accessible articles. Filtered by customer visibility when authenticated.",
    auth: "api-key", tags: ["Articles"],
    params: [{ name: "category", in: "query", type: "string", description: "Filter by category", example: "Help" }],
    responseExample: { articles: [{ id: "art_xxx", title: "Getting Started", slug: "getting-started", category: "Guide" }] },
  },
  {
    method: "GET", path: "/api/articles/{id}", summary: "Get article by ID",
    description: "Returns the full content of a specific article.",
    auth: "api-key", tags: ["Articles"],
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Article ID", example: "art_abc123" }],
    responseExample: { article: { id: "art_xxx", title: "Getting Started", content: "<h1>Welcome</h1>..." } },
  },
  // ── Quote Requests ────────────────────────────────────────────────────────
  {
    method: "POST", path: "/api/orders/scope-request-form", summary: "Submit a quote / scope request",
    description: "Submit a scope request with form fields. No authentication required.",
    auth: "api-key", tags: ["Requests"],
    bodySchema: { product_id: "string", fields: [{ key: "string", value: "string" }] },
    responseExample: { success: true, message: "Your request has been received" },
  },
  {
    method: "POST", path: "/api/promo-codes/validate", summary: "Validate a promo code",
    description: "Check if a promo code is valid and return its discount details. Requires customer authentication.",
    auth: "bearer", tags: ["Checkout"],
    bodySchema: { code: "string" },
    responseExample: { valid: true, discount_type: "percentage", discount_value: 20 },
  },
  // ── Customer Portal ───────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/me", summary: "Get current user profile",
    description: "Returns the authenticated customer's profile, customer record, and address.",
    auth: "bearer", tags: ["Customer Portal"],
    responseExample: { user: { id: "usr_xxx", email: "customer@example.com", full_name: "Jane Smith" }, customer: {}, address: {} },
  },
  {
    method: "PUT", path: "/api/me", summary: "Update customer profile",
    description: "Update the authenticated customer's name, company, phone, and address.",
    auth: "bearer", tags: ["Customer Portal"],
    bodySchema: { full_name: "string (optional)", company_name: "string (optional)", phone: "string (optional)", address: { line1: "", city: "", postal: "", country: "" } },
    responseExample: { success: true },
  },
  {
    method: "GET", path: "/api/subscriptions", summary: "List customer subscriptions",
    description: "Returns all active subscriptions for the authenticated customer.",
    auth: "bearer", tags: ["Customer Portal"],
    responseExample: { subscriptions: [{ id: "sub_xxx", product_name: "Starter Package", status: "active", next_billing_date: "2026-03-01" }] },
  },
  {
    method: "GET", path: "/api/orders", summary: "List customer orders",
    description: "Returns all orders for the authenticated customer.",
    auth: "bearer", tags: ["Customer Portal"],
    responseExample: { orders: [{ id: "ord_xxx", order_number: "ORD-001", status: "complete", total_amount: 499 }] },
  },
  {
    method: "POST", path: "/api/subscriptions/{id}/cancel", summary: "Cancel a subscription",
    description: "Cancel a specific subscription for the authenticated customer.",
    auth: "bearer", tags: ["Customer Portal"],
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Subscription ID" }],
    bodySchema: { reason: "string (optional)" },
    responseExample: { success: true, message: "Subscription cancelled" },
  },
];

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-emerald-100 text-emerald-700",
  POST: "bg-blue-100 text-blue-700",
  PUT: "bg-amber-100 text-amber-700",
  DELETE: "bg-red-100 text-red-700",
  PATCH: "bg-purple-100 text-purple-700",
};

const AUTH_BADGE: Record<string, { label: string; color: string }> = {
  none: { label: "Public", color: "bg-slate-100 text-slate-500" },
  "api-key": { label: "X-API-Key", color: "bg-indigo-100 text-indigo-700" },
  bearer: { label: "Bearer JWT", color: "bg-orange-100 text-orange-700" },
};

// ── Endpoint Accordion ────────────────────────────────────────────────────────

function EndpointCard({ ep, apiKey }: { ep: EndpointDef; apiKey: string }) {
  const [open, setOpen] = useState(false);
  const [tryOpen, setTryOpen] = useState(false);
  const [tryInputs, setTryInputs] = useState<Record<string, string>>({});
  const [tryBody, setTryBody] = useState(ep.bodySchema ? JSON.stringify(ep.bodySchema, null, 2) : "");
  const [tryResult, setTryResult] = useState<{ status: number; body: any } | null>(null);
  const [trying, setTrying] = useState(false);

  const ab = AUTH_BADGE[ep.auth];

  const handleTry = async () => {
    setTrying(true);
    setTryResult(null);
    try {
      const base = process.env.REACT_APP_BACKEND_URL || "";
      let url = base + ep.path;
      // Replace path params
      const pathParams = (ep.params || []).filter(p => p.in === "path");
      for (const p of pathParams) url = url.replace(`{${p.name}}`, tryInputs[p.name] || `:${p.name}`);
      // Query params
      const qp = (ep.params || []).filter(p => p.in === "query").filter(p => tryInputs[p.name]);
      if (qp.length) url += "?" + qp.map(p => `${p.name}=${encodeURIComponent(tryInputs[p.name])}`).join("&");

      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (ep.auth === "api-key" && apiKey) headers["X-API-Key"] = apiKey;
      if (ep.auth === "bearer") {
        const token = localStorage.getItem("aa_token") || "";
        if (token) headers["Authorization"] = `Bearer ${token}`;
      }

      let body: string | undefined;
      if (ep.bodySchema && tryBody.trim()) {
        try { body = tryBody; } catch { body = undefined; }
      }

      const resp = await fetch(url, { method: ep.method, headers, body: ep.method !== "GET" ? body : undefined });
      const data = await resp.json().catch(() => ({}));
      setTryResult({ status: resp.status, body: data });
    } catch (e: any) {
      setTryResult({ status: 0, body: { error: e.message } });
    } finally {
      setTrying(false);
    }
  };

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 bg-white hover:bg-slate-50 transition-colors text-left"
        data-testid={`endpoint-${ep.method.toLowerCase()}-${ep.path.replace(/\//g, "-")}`}
      >
        <span className={`text-[11px] font-bold px-2 py-0.5 rounded font-mono min-w-[48px] text-center ${METHOD_COLORS[ep.method]}`}>{ep.method}</span>
        <span className="font-mono text-sm text-slate-700 flex-1">{ep.path}</span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${ab.color}`}>{ab.label}</span>
        {open ? <ChevronDown size={14} className="text-slate-400 shrink-0" /> : <ChevronRight size={14} className="text-slate-400 shrink-0" />}
      </button>

      {open && (
        <div className="border-t border-slate-100 bg-slate-50 p-4 space-y-4">
          <div>
            <p className="text-sm font-semibold text-slate-800">{ep.summary}</p>
            <p className="text-xs text-slate-500 mt-1">{ep.description}</p>
          </div>

          {/* Auth */}
          <div className="flex items-center gap-2">
            <Key size={12} className="text-slate-400" />
            <span className="text-xs text-slate-500">Authentication:</span>
            <span className={`text-[11px] px-2 py-0.5 rounded font-medium ${ab.color}`}>{ab.label}</span>
            {ep.auth === "api-key" && <span className="text-xs text-slate-400">— Pass <code className="bg-white border px-1 rounded font-mono">X-API-Key: &lt;your-key&gt;</code> header</span>}
            {ep.auth === "bearer" && <span className="text-xs text-slate-400">— Pass <code className="bg-white border px-1 rounded font-mono">Authorization: Bearer &lt;jwt&gt;</code> header</span>}
          </div>

          {/* Params */}
          {ep.params && ep.params.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Parameters</p>
              <div className="rounded-lg overflow-hidden border border-slate-200">
                <table className="w-full text-xs">
                  <thead className="bg-white">
                    <tr className="border-b border-slate-100">
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Name</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">In</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Type</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Required</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ep.params.map(p => (
                      <tr key={p.name} className="border-b border-slate-100 last:border-0 bg-white">
                        <td className="px-3 py-2 font-mono text-slate-800">{p.name}</td>
                        <td className="px-3 py-2 text-slate-500">{p.in}</td>
                        <td className="px-3 py-2 text-slate-500">{p.type}</td>
                        <td className="px-3 py-2">{p.required ? <span className="text-red-500">Yes</span> : <span className="text-slate-400">No</span>}</td>
                        <td className="px-3 py-2 text-slate-500">{p.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Body schema */}
          {ep.bodySchema && (
            <div>
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Request Body</p>
              <pre className="bg-slate-900 text-green-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
                {JSON.stringify(ep.bodySchema, null, 2)}
              </pre>
            </div>
          )}

          {/* Response */}
          {ep.responseExample && (
            <div>
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Example Response</p>
              <pre className="bg-slate-900 text-blue-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
                {JSON.stringify(ep.responseExample, null, 2)}
              </pre>
            </div>
          )}

          {/* Try it */}
          <div className="border-t border-slate-200 pt-3">
            <button onClick={() => setTryOpen(v => !v)} className="flex items-center gap-2 text-xs font-semibold text-slate-700 hover:text-slate-900">
              <Play size={12} />
              {tryOpen ? "Hide Try It" : "Try It"}
            </button>
            {tryOpen && (
              <div className="mt-3 space-y-3">
                {/* Path/query inputs */}
                {(ep.params || []).filter(p => p.in !== "header").map(p => (
                  <div key={p.name}>
                    <label className="text-xs text-slate-500">{p.name} ({p.in}){p.required ? " *" : ""}</label>
                    <Input
                      placeholder={p.example || `Enter ${p.name}`}
                      value={tryInputs[p.name] || ""}
                      onChange={e => setTryInputs(prev => ({ ...prev, [p.name]: e.target.value }))}
                      className="mt-1 h-8 text-xs font-mono"
                    />
                  </div>
                ))}
                {ep.bodySchema && (
                  <div>
                    <label className="text-xs text-slate-500">Request Body (JSON)</label>
                    <textarea
                      value={tryBody}
                      onChange={e => setTryBody(e.target.value)}
                      rows={5}
                      className="mt-1 w-full text-xs font-mono border border-slate-200 rounded-lg p-2 bg-white resize-y"
                    />
                  </div>
                )}
                <Button size="sm" onClick={handleTry} disabled={trying} className="gap-2">
                  <Play size={12} />
                  {trying ? "Sending…" : "Send Request"}
                </Button>
                {tryResult && (
                  <div className={`rounded-lg overflow-hidden border ${tryResult.status >= 200 && tryResult.status < 300 ? "border-green-200" : "border-red-200"}`}>
                    <div className={`px-3 py-1.5 text-xs font-mono font-semibold ${tryResult.status >= 200 && tryResult.status < 300 ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                      HTTP {tryResult.status || "Error"}
                    </div>
                    <pre className="bg-slate-900 text-slate-200 text-[11px] font-mono p-3 overflow-x-auto max-h-64">
                      {JSON.stringify(tryResult.body, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── API Key Manager ───────────────────────────────────────────────────────────

function ApiKeyManager() {
  const [keys, setKeys] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [newKeyName, setNewKeyName] = useState("Production Key");
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const revealRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/api-keys");
      setKeys(res.data.api_keys || []);
    } catch { toast.error("Failed to load API keys"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleGenerate = async () => {
    if (!window.confirm("Generating a new key will revoke all existing active keys for this tenant. Continue?")) return;
    setGenerating(true);
    try {
      const res = await api.post("/admin/api-keys", { name: newKeyName });
      setRevealedKey(res.data.key);
      await load();
      toast.success("New API key generated. Copy it now!");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to generate key");
    } finally {
      setGenerating(false);
    }
  };

  const handleRevoke = async (keyId: string, name: string) => {
    if (!window.confirm(`Revoke key "${name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/admin/api-keys/${keyId}`);
      toast.success("API key revoked");
      load();
    } catch { toast.error("Failed to revoke key"); }
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key).then(() => toast.success("Copied to clipboard"));
  };

  return (
    <div className="space-y-5">
      {/* Revealed new key banner */}
      {revealedKey && (
        <div className="rounded-xl bg-amber-50 border border-amber-300 p-4 space-y-2">
          <p className="text-sm font-semibold text-amber-800">Your new API key — copy it now!</p>
          <p className="text-xs text-amber-700">This key will not be shown again. Store it securely.</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-white border border-amber-200 rounded px-3 py-2 text-sm font-mono text-amber-900 break-all" data-testid="new-api-key-value">{revealedKey}</code>
            <Button size="sm" variant="outline" className="shrink-0" onClick={() => copyKey(revealedKey)} data-testid="copy-api-key-btn">
              <Copy size={13} className="mr-1" /> Copy
            </Button>
          </div>
          <Button size="sm" variant="ghost" className="text-amber-700 text-xs" onClick={() => setRevealedKey(null)}>Dismiss</Button>
        </div>
      )}

      {/* Active keys */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm font-semibold text-slate-800">API Keys</p>
            <p className="text-xs text-slate-500 mt-0.5">One active key per tenant. Generating a new key revokes existing ones.</p>
          </div>
          <Button size="sm" variant="outline" onClick={() => setShowNew(v => !v)} data-testid="generate-api-key-btn">
            <RefreshCw size={13} className="mr-1.5" /> {keys.some(k => k.is_active) ? "Regenerate" : "Generate"} Key
          </Button>
        </div>

        {showNew && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 mb-4 space-y-3">
            <p className="text-xs font-semibold text-slate-600">Key Name (optional)</p>
            <Input value={newKeyName} onChange={e => setNewKeyName(e.target.value)} placeholder="e.g. Production Key" className="h-8 text-sm" data-testid="api-key-name-input" />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleGenerate} disabled={generating} data-testid="confirm-generate-key-btn">
                {generating ? "Generating…" : "Generate Key"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowNew(false)}>Cancel</Button>
            </div>
          </div>
        )}

        {loading ? (
          <p className="text-xs text-slate-400 py-4">Loading…</p>
        ) : keys.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center">
            <Key size={24} className="mx-auto text-slate-300 mb-2" />
            <p className="text-sm text-slate-500">No API keys yet.</p>
            <p className="text-xs text-slate-400 mt-1">Generate your first key to start integrating.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {keys.map((k) => (
              <div key={k.id} className={`rounded-xl border p-4 flex items-center gap-4 ${k.is_active ? "border-slate-200 bg-white" : "border-slate-100 bg-slate-50 opacity-60"}`} data-testid={`api-key-row-${k.id}`}>
                <div className={`h-2 w-2 rounded-full shrink-0 ${k.is_active ? "bg-green-500" : "bg-slate-300"}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-slate-800">{k.name || "API Key"}</p>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${k.is_active ? "bg-green-100 text-green-700" : "bg-slate-200 text-slate-500"}`}>
                      {k.is_active ? "Active" : "Revoked"}
                    </span>
                  </div>
                  <p className="text-xs font-mono text-slate-400 mt-0.5">{k.key_masked || "•••••••••••••••"}</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">Created {new Date(k.created_at).toLocaleDateString()} {k.last_used_at ? `· Last used ${new Date(k.last_used_at).toLocaleDateString()}` : "· Never used"}</p>
                </div>
                {k.is_active && (
                  <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-600 shrink-0" onClick={() => handleRevoke(k.id, k.name)} data-testid={`revoke-key-${k.id}`}>
                    <Trash2 size={13} />
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Tab Component ────────────────────────────────────────────────────────

const ALL_TAGS = [...new Set(API_ENDPOINTS.flatMap(e => e.tags))];

export function ApiTab() {
  const [activeTag, setActiveTag] = useState<string>("All");
  const [searchTerm, setSearchTerm] = useState("");
  const [activeSection, setActiveSection] = useState<"keys" | "docs">("keys");

  const filtered = API_ENDPOINTS.filter(ep => {
    const matchTag = activeTag === "All" || ep.tags.includes(activeTag);
    const matchSearch = !searchTerm || ep.path.toLowerCase().includes(searchTerm.toLowerCase()) || ep.summary.toLowerCase().includes(searchTerm.toLowerCase());
    return matchTag && matchSearch;
  });

  // Get current API key for try-it feature
  const [currentKey, setCurrentKey] = useState("");
  useEffect(() => {
    api.get("/admin/api-keys").then(res => {
      const active = (res.data.api_keys || []).find((k: any) => k.is_active);
      if (active) setCurrentKey(active.key_masked || "");
    }).catch(() => {});
  }, []);

  return (
    <div className="space-y-6" data-testid="api-tab">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">API</h2>
          <p className="text-sm text-slate-500 mt-0.5">Manage your API key and explore available endpoints for integration.</p>
        </div>
        <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
          <button
            onClick={() => setActiveSection("keys")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${activeSection === "keys" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
            data-testid="api-section-keys"
          >
            <Key size={12} className="inline mr-1.5" />API Keys
          </button>
          <button
            onClick={() => setActiveSection("docs")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${activeSection === "docs" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
            data-testid="api-section-docs"
          >
            <BookOpen size={12} className="inline mr-1.5" />Documentation
          </button>
        </div>
      </div>

      {activeSection === "keys" && (
        <div className="space-y-6">
          <ApiKeyManager />

          {/* Quick-start guide */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <p className="text-sm font-semibold text-slate-800">Quick Start</p>
            <div className="space-y-3">
              <div>
                <p className="text-xs font-medium text-slate-600 mb-1">1. Set the API Key header on every request:</p>
                <pre className="bg-slate-900 text-green-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
{`X-API-Key: ak_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`}
                </pre>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-600 mb-1">2. Use relative paths — your base URL depends on your subdomain:</p>
                <pre className="bg-slate-900 text-blue-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
{`# Example base URL (replace with your actual subdomain)
GET https://your-subdomain.example.com/api/products
     ──────────────────────────────── ────────────
     Your base URL                    API path`}
                </pre>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-600 mb-1">3. Authenticated (customer) endpoints also need a Bearer JWT token:</p>
                <pre className="bg-slate-900 text-amber-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
{`Authorization: Bearer <token from POST /api/auth/customer-login>`}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeSection === "docs" && (
        <div className="flex gap-5">
          {/* Tag filter sidebar */}
          <div className="w-44 shrink-0 space-y-1">
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 pb-1">Filter by tag</p>
            {["All", ...ALL_TAGS].map(tag => (
              <button key={tag} onClick={() => setActiveTag(tag)}
                className={`w-full text-left px-3 py-2 text-xs rounded-lg transition-colors ${activeTag === tag ? "bg-slate-900 text-white font-medium" : "text-slate-600 hover:bg-slate-100"}`}
                data-testid={`api-tag-${tag.toLowerCase().replace(/\s+/g, "-")}`}
              >
                {tag}
              </button>
            ))}
          </div>

          {/* Endpoints list */}
          <div className="flex-1 min-w-0 space-y-3">
            <div className="flex items-center gap-2">
              <Input
                placeholder="Search endpoints…"
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="h-8 text-xs w-64"
                data-testid="api-search-input"
              />
              <span className="text-xs text-slate-400">{filtered.length} endpoint{filtered.length !== 1 ? "s" : ""}</span>
            </div>

            {/* Base URL note */}
            <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 flex items-start gap-3">
              <ExternalLink size={14} className="text-blue-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-blue-800">Base URL</p>
                <p className="text-xs text-blue-600 mt-0.5">
                  All paths below are relative. Prepend your tenant's base URL: <code className="bg-blue-100 px-1 rounded font-mono">https://your-domain.com</code> or your custom subdomain.
                </p>
              </div>
            </div>

            {filtered.map((ep, i) => <EndpointCard key={i} ep={ep} apiKey={currentKey} />)}
          </div>
        </div>
      )}
    </div>
  );
}
