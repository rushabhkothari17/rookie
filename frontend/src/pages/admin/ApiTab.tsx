import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";
import { Copy, RefreshCw, Trash2, ChevronDown, ChevronRight, Play, Key, BookOpen, Info, AlertCircle } from "lucide-react";
import api from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Param {
  name: string;
  in: "query" | "path" | "header" | "body";
  type: string;
  required?: boolean;
  description: string;
  example?: string;
}

interface EndpointDef {
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  path: string;
  summary: string;
  description: string;
  /** "api-key" = X-API-Key only; "customer-jwt" = X-API-Key + Bearer JWT */
  auth: "api-key" | "customer-jwt";
  tags: string[];
  params?: Param[];
  bodySchema?: Record<string, any>;
  responseExample?: Record<string, any>;
}

// ── Endpoint Definitions ──────────────────────────────────────────────────────

const API_ENDPOINTS: EndpointDef[] = [
  // ── Authentication ────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/tenant-info", auth: "api-key", tags: ["Authentication"],
    summary: "Verify API Key / Get tenant info",
    description: "Verify your API key is valid and return basic tenant information.",
    responseExample: { tenant_id: "your-tenant-id", name: "Your Company Ltd", code: "your-partner-code" },
  },
  {
    method: "POST", path: "/api/auth/customer-login", auth: "api-key", tags: ["Authentication"],
    summary: "Login as customer (get JWT)",
    description: "Authenticate a customer with email and password. Returns a JWT token used for all customer-specific endpoints. Pass X-API-Key to identify the tenant.",
    bodySchema: { email: "string", password: "string" },
    responseExample: { token: "eyJhbGci...", role: "customer", tenant_id: "your-tenant-id" },
  },
  {
    method: "POST", path: "/api/auth/register", auth: "api-key", tags: ["Authentication"],
    summary: "Register a new customer",
    description: "Register a new customer account under your tenant. A verification email is sent.",
    bodySchema: { email: "string", password: "string", full_name: "string", company_name: "string (optional)" },
    responseExample: { success: true, message: "Verification email sent" },
  },
  {
    method: "POST", path: "/api/auth/verify-email", auth: "api-key", tags: ["Authentication"],
    summary: "Verify customer email",
    description: "Verify a customer's email address using the token sent in the verification email.",
    bodySchema: { token: "string" },
    responseExample: { success: true, message: "Email verified" },
  },
  {
    method: "POST", path: "/api/auth/resend-verification-email", auth: "api-key", tags: ["Authentication"],
    summary: "Resend verification email",
    description: "Resend the email verification link to an unverified customer.",
    bodySchema: { email: "string" },
    responseExample: { success: true },
  },
  // ── Catalog ───────────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/categories", auth: "api-key", tags: ["Catalog"],
    summary: "List product categories",
    description: "Returns all active product categories with optional blurb text.",
    responseExample: { categories: ["Bookkeeping", "Tax Returns"], category_blurbs: { "Bookkeeping": "Monthly bookkeeping services" } },
  },
  {
    method: "GET", path: "/api/products", auth: "api-key", tags: ["Catalog"],
    summary: "List all products",
    description: "Returns all active, publicly visible products. When called with a customer JWT, respects customer-level visibility restrictions.",
    responseExample: { products: [{ id: "prod_xxx", name: "Starter Package", base_price: 499, billing_period: "monthly", category: "Bookkeeping" }] },
  },
  {
    method: "GET", path: "/api/products/{id}", auth: "api-key", tags: ["Catalog"],
    summary: "Get product details",
    description: "Returns full product details including pricing schema and intake fields. Use intake_schema_json to build a dynamic quote form.",
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Product ID", example: "prod_abc123" }],
    responseExample: { product: { id: "prod_xxx", name: "Starter Package", pricing_type: "dynamic", billing_period: "monthly", intake_schema_json: [] } },
  },
  {
    method: "POST", path: "/api/pricing/calc", auth: "customer-jwt", tags: ["Catalog"],
    summary: "Calculate dynamic pricing",
    description: "Calculate the price for a product given customer-specific inputs. Use the product's intake_schema_json to determine required inputs. Requires customer JWT.",
    bodySchema: { product_id: "string", inputs: { field_name: "value" } },
    responseExample: { product_id: "prod_xxx", total: 699, line_items: [{ label: "Base fee", amount: 499 }] },
  },
  // ── Terms & Conditions ─────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/terms", auth: "api-key", tags: ["Terms & Conditions"],
    summary: "List T&C documents",
    description: "Returns all Terms & Conditions documents published by the tenant.",
    responseExample: { terms: [{ id: "terms_xxx", title: "Standard Service Agreement", version: "1.0", created_at: "2026-01-01T00:00:00Z" }] },
  },
  {
    method: "GET", path: "/api/terms/{id}", auth: "api-key", tags: ["Terms & Conditions"],
    summary: "Get T&C by ID",
    description: "Returns the full content of a specific Terms & Conditions document.",
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Terms document ID", example: "terms_abc123" }],
    responseExample: { terms: { id: "terms_xxx", title: "Standard Service Agreement", version: "1.0", content: "<h1>Terms</h1>..." } },
  },
  // ── Articles ──────────────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/articles/public", auth: "api-key", tags: ["Articles"],
    summary: "List published articles",
    description: "Returns all published, public articles. When called with a customer JWT, returns articles visible to that customer based on subscription scope.",
    params: [{ name: "category", in: "query", type: "string", required: false, description: "Filter by category slug", example: "guides" }],
    responseExample: { articles: [{ id: "art_xxx", title: "Getting Started", category: "Guides", published: true }] },
  },
  {
    method: "GET", path: "/api/articles/{id}", auth: "api-key", tags: ["Articles"],
    summary: "Get article by ID",
    description: "Returns the full HTML content of a specific article.",
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Article ID", example: "art_abc123" }],
    responseExample: { article: { id: "art_xxx", title: "Getting Started", content: "<h1>Welcome</h1>...", category: "Guides" } },
  },
  {
    method: "GET", path: "/api/article-categories/public", auth: "api-key", tags: ["Articles"],
    summary: "List article categories",
    description: "Returns all article categories available for the tenant.",
    responseExample: { categories: [{ id: "cat_xxx", name: "Guides", slug: "guides", color: "#1e40af" }] },
  },
  // ── Quote / Scope Requests ────────────────────────────────────────────────
  {
    method: "POST", path: "/api/orders/scope-request-form", auth: "api-key", tags: ["Quote Requests"],
    summary: "Submit a quote request",
    description: "Submit a scope/quote request. No customer authentication required — suitable for anonymous forms. Associates the request with the tenant via X-API-Key.",
    bodySchema: { product_id: "string", fields: [{ key: "string", value: "string" }] },
    responseExample: { success: true, message: "Your request has been received", request_id: "req_xxx" },
  },
  {
    method: "POST", path: "/api/orders/preview", auth: "customer-jwt", tags: ["Quote Requests"],
    summary: "Preview order pricing",
    description: "Calculate and preview the full pricing for a potential order before checkout. Requires customer JWT.",
    bodySchema: { product_id: "string", promo_code: "string (optional)", intake_answers: {} },
    responseExample: { subtotal: 499, discount: 50, fee: 10, total: 459, line_items: [] },
  },
  {
    method: "POST", path: "/api/promo-codes/validate", auth: "customer-jwt", tags: ["Quote Requests"],
    summary: "Validate a promo code",
    description: "Check if a promo code is valid and return its discount details. Requires customer JWT.",
    bodySchema: { code: "string" },
    responseExample: { valid: true, discount_type: "percentage", discount_value: 20, applies_to: "all" },
  },
  // ── Checkout ──────────────────────────────────────────────────────────────
  {
    method: "POST", path: "/api/checkout/session", auth: "customer-jwt", tags: ["Checkout"],
    summary: "Create Stripe checkout session",
    description: "Create a Stripe-hosted checkout session for a product. Returns a redirect URL to the Stripe payment page.",
    bodySchema: { product_id: "string", promo_code: "string (optional)", terms_accepted: true, intake_answers: {}, pricing_answers: {} },
    responseExample: { url: "https://checkout.stripe.com/...", session_id: "cs_xxx", order_id: "ord_xxx" },
  },
  {
    method: "GET", path: "/api/checkout/status/{session_id}", auth: "customer-jwt", tags: ["Checkout"],
    summary: "Get checkout session status",
    description: "Check the status of a Stripe checkout session after the customer returns from the payment page.",
    params: [{ name: "session_id", in: "path", type: "string", required: true, description: "Stripe session ID", example: "cs_xxx" }],
    responseExample: { status: "paid", order_id: "ord_xxx", amount_total: 49900, currency: "usd" },
  },
  {
    method: "POST", path: "/api/checkout/bank-transfer", auth: "customer-jwt", tags: ["Checkout"],
    summary: "Initiate GoCardless Direct Debit",
    description: "Create a GoCardless Direct Debit setup for a subscription. Returns a redirect URL for the customer to complete bank authorisation.",
    bodySchema: { product_id: "string", promo_code: "string (optional)", terms_accepted: true, intake_answers: {} },
    responseExample: { order_id: "ord_xxx", gocardless_redirect_url: "https://pay.gocardless.com/...", status: "pending_direct_debit_setup" },
  },
  // ── Customer Profile ──────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/me", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "Get current user profile",
    description: "Returns the authenticated customer's profile, customer record, and address.",
    responseExample: { user: { id: "usr_xxx", email: "jane@example.com", full_name: "Jane Smith", partner_code: "your-partner-code" }, customer: {}, address: {} },
  },
  {
    method: "PUT", path: "/api/me", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "Update customer profile",
    description: "Update the authenticated customer's name, company, phone, and address.",
    bodySchema: { full_name: "string (optional)", company_name: "string (optional)", phone: "string (optional)", address: { line1: "", city: "", postal: "", country: "" } },
    responseExample: { success: true },
  },
  // ── Customer Orders ───────────────────────────────────────────────────────
  {
    method: "GET", path: "/api/orders", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "List customer orders",
    description: "Returns all orders for the authenticated customer, including line items.",
    responseExample: { orders: [{ id: "ord_xxx", order_number: "ORD-001", status: "complete", total_amount: 499 }], items: [] },
  },
  {
    method: "GET", path: "/api/orders/{id}", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "Get order details",
    description: "Returns full details of a specific order including all line items.",
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Order ID", example: "ord_abc123" }],
    responseExample: { order: { id: "ord_xxx", order_number: "ORD-001", status: "complete", total_amount: 499 }, items: [{ product_name: "Starter Package", quantity: 1, amount: 499 }] },
  },
  // ── Customer Subscriptions ────────────────────────────────────────────────
  {
    method: "GET", path: "/api/subscriptions", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "List customer subscriptions",
    description: "Returns all subscriptions for the authenticated customer.",
    responseExample: { subscriptions: [{ id: "sub_xxx", product_name: "Starter Package", status: "active", billing_period: "monthly", next_billing_date: "2026-04-01" }] },
  },
  {
    method: "POST", path: "/api/subscriptions/{id}/cancel", auth: "customer-jwt", tags: ["Customer Portal"],
    summary: "Cancel a subscription",
    description: "Request cancellation of a subscription. The subscription will remain active until the end of the current billing period.",
    params: [{ name: "id", in: "path", type: "string", required: true, description: "Subscription ID", example: "sub_abc123" }],
    bodySchema: { reason: "string (optional)" },
    responseExample: { success: true, message: "Subscription will be cancelled at end of billing period", cancel_at_period_end: true },
  },
];

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-emerald-100 text-emerald-700",
  POST: "bg-blue-100 text-blue-700",
  PUT: "bg-amber-100 text-amber-700",
  DELETE: "bg-red-100 text-red-700",
  PATCH: "bg-purple-100 text-purple-700",
};

const ALL_TAGS = Array.from(new Set(API_ENDPOINTS.flatMap(e => e.tags)));

// ── Endpoint Card ─────────────────────────────────────────────────────────────

function EndpointCard({ ep, testApiKey }: { ep: EndpointDef; testApiKey: string }) {
  const [open, setOpen] = useState(false);
  const [tryOpen, setTryOpen] = useState(false);
  const [tryInputs, setTryInputs] = useState<Record<string, string>>({});
  const [tryBody, setTryBody] = useState(ep.bodySchema ? JSON.stringify(ep.bodySchema, null, 2) : "");
  const [tryJwt, setTryJwt] = useState("");
  const [tryResult, setTryResult] = useState<{ status: number; body: any } | null>(null);
  const [trying, setTrying] = useState(false);

  const handleTry = async () => {
    if (!testApiKey.trim()) {
      toast.error("Enter your API key in the field above before using Try It.");
      return;
    }
    setTrying(true);
    setTryResult(null);
    try {
      const base = process.env.REACT_APP_BACKEND_URL || "";
      let url = base + ep.path;
      const pathParams = (ep.params || []).filter(p => p.in === "path");
      for (const p of pathParams) url = url.replace(`{${p.name}}`, tryInputs[p.name] || `:${p.name}`);
      const qp = (ep.params || []).filter(p => p.in === "query").filter(p => tryInputs[p.name]);
      if (qp.length) url += "?" + qp.map(p => `${p.name}=${encodeURIComponent(tryInputs[p.name])}`).join("&");

      const headers: Record<string, string> = { "Content-Type": "application/json", "X-API-Key": testApiKey.trim() };
      if (ep.auth === "customer-jwt" && tryJwt.trim()) {
        headers["Authorization"] = `Bearer ${tryJwt.trim()}`;
      }

      let body: string | undefined;
      if (ep.bodySchema && tryBody.trim() && ep.method !== "GET") body = tryBody;

      const resp = await fetch(url, { method: ep.method, headers, body });
      const data = await resp.json().catch(() => ({}));
      setTryResult({ status: resp.status, body: data });
    } catch (e: any) {
      setTryResult({ status: 0, body: { error: e.message } });
    } finally {
      setTrying(false);
    }
  };

  const authBadge = ep.auth === "api-key"
    ? <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-indigo-100 text-indigo-700">X-API-Key</span>
    : <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-orange-100 text-orange-700">X-API-Key + JWT</span>;

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden" data-testid={`endpoint-card-${ep.method}-${ep.path.replace(/\//g, "-").replace(/[{}]/g, "")}`}>
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 bg-white hover:bg-slate-50 transition-colors text-left"
      >
        <span className={`text-[11px] font-bold px-2 py-0.5 rounded font-mono min-w-[48px] text-center ${METHOD_COLORS[ep.method]}`}>{ep.method}</span>
        <span className="font-mono text-sm text-slate-700 flex-1 truncate">{ep.path}</span>
        {authBadge}
        {open ? <ChevronDown size={14} className="text-slate-400 shrink-0" /> : <ChevronRight size={14} className="text-slate-400 shrink-0" />}
      </button>

      {open && (
        <div className="border-t border-slate-100 bg-slate-50 p-4 space-y-4">
          <div>
            <p className="text-sm font-semibold text-slate-800">{ep.summary}</p>
            <p className="text-xs text-slate-500 mt-1">{ep.description}</p>
          </div>

          {/* Auth requirements */}
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 space-y-1.5">
            <p className="text-xs font-semibold text-slate-600">Authentication</p>
            <div className="flex items-center gap-2 text-xs text-slate-600">
              <Key size={12} className="text-indigo-500 shrink-0" />
              <span>Always required:</span>
              <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">X-API-Key: ak_…</code>
            </div>
            {ep.auth === "customer-jwt" && (
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <Key size={12} className="text-orange-500 shrink-0" />
                <span>Also required:</span>
                <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">Authorization: Bearer &lt;customer-jwt&gt;</code>
              </div>
            )}
          </div>

          {/* Parameters */}
          {ep.params && ep.params.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Parameters</p>
              <div className="rounded-lg overflow-hidden border border-slate-200">
                <table className="w-full text-xs">
                  <thead className="bg-white border-b border-slate-100">
                    <tr>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Name</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">In</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Type</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Req.</th>
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

          {/* Body */}
          {ep.bodySchema && (
            <div>
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Request Body (JSON)</p>
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

          {/* Try It */}
          <div className="border-t border-slate-200 pt-3">
            <button onClick={() => setTryOpen(v => !v)} className="flex items-center gap-2 text-xs font-semibold text-slate-700 hover:text-indigo-600 transition-colors">
              <Play size={12} />
              {tryOpen ? "Hide Try It" : "Try It Live"}
            </button>

            {tryOpen && (
              <div className="mt-3 space-y-3">
                {ep.auth === "customer-jwt" && (
                  <div>
                    <label className="text-xs font-medium text-orange-700">Customer JWT (from /api/auth/customer-login)</label>
                    <Input placeholder="eyJhbGci…" value={tryJwt} onChange={e => setTryJwt(e.target.value)} className="mt-1 h-8 text-xs font-mono" />
                  </div>
                )}

                {(ep.params || []).filter(p => p.in !== "header").map(p => (
                  <div key={p.name}>
                    <label className="text-xs text-slate-500">{p.name} ({p.in}){p.required ? " *" : ""}</label>
                    <Input placeholder={p.example || `Enter ${p.name}`} value={tryInputs[p.name] || ""} onChange={e => setTryInputs(prev => ({ ...prev, [p.name]: e.target.value }))} className="mt-1 h-8 text-xs font-mono" />
                  </div>
                ))}

                {ep.bodySchema && (
                  <div>
                    <label className="text-xs text-slate-500">Request Body (JSON)</label>
                    <textarea value={tryBody} onChange={e => setTryBody(e.target.value)} rows={5} className="mt-1 w-full text-xs font-mono border border-slate-200 rounded-lg p-2 bg-white resize-y" />
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

function ApiKeyManager({ onKeyResolved }: { onKeyResolved: (key: string) => void }) {
  const [keys, setKeys] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [newKeyName, setNewKeyName] = useState("Production Key");
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);

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
    if (!window.confirm("Generating a new key will revoke the existing active key for this tenant. Continue?")) return;
    setGenerating(true);
    try {
      const res = await api.post("/admin/api-keys", { name: newKeyName });
      setRevealedKey(res.data.key);
      await load();
      toast.success("New API key generated. Copy it now — it won't be shown again.");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to generate key");
    } finally {
      setGenerating(false);
      setShowNew(false);
    }
  };

  const handleRevoke = async (keyId: string, name: string) => {
    if (!window.confirm(`Revoke key "${name}"? All integrations using this key will stop working immediately.`)) return;
    try {
      await api.delete(`/admin/api-keys/${keyId}`);
      toast.success("API key revoked");
      setRevealedKey(null);
      load();
    } catch { toast.error("Failed to revoke key"); }
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key).then(() => toast.success("Copied to clipboard"));
    onKeyResolved(key);
  };

  const activeKey = keys.find(k => k.is_active);

  return (
    <div className="space-y-5">
      {/* Revealed new key banner */}
      {revealedKey && (
        <div className="rounded-xl bg-amber-50 border border-amber-300 p-4 space-y-2">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="text-amber-600" />
            <p className="text-sm font-semibold text-amber-800">Your new API key — copy it now!</p>
          </div>
          <p className="text-xs text-amber-700">This key will not be shown again. Store it in a secure location (e.g. environment variables, a secrets manager).</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-white border border-amber-200 rounded px-3 py-2 text-sm font-mono text-amber-900 break-all" data-testid="new-api-key-value">{revealedKey}</code>
            <Button size="sm" variant="outline" className="shrink-0" onClick={() => copyKey(revealedKey)} data-testid="copy-api-key-btn">
              <Copy size={13} className="mr-1" /> Copy & Use
            </Button>
          </div>
          <Button size="sm" variant="ghost" className="text-amber-700 text-xs" onClick={() => setRevealedKey(null)}>Dismiss</Button>
        </div>
      )}

      {/* Current active key */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm font-semibold text-slate-800">Active API Key</p>
            <p className="text-xs text-slate-500 mt-0.5">One key per tenant. Generating a new key immediately revokes the current one.</p>
          </div>
          <Button size="sm" variant="outline" onClick={() => setShowNew(v => !v)} data-testid="generate-api-key-btn">
            <RefreshCw size={13} className="mr-1.5" />
            {activeKey ? "Regenerate Key" : "Generate Key"}
          </Button>
        </div>

        {showNew && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 mb-4 space-y-3">
            <p className="text-xs font-semibold text-slate-600">Key Label (optional)</p>
            <Input value={newKeyName} onChange={e => setNewKeyName(e.target.value)} placeholder="e.g. Production" className="h-8 text-sm" data-testid="api-key-name-input" />
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
        ) : !activeKey ? (
          <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center">
            <Key size={24} className="mx-auto text-slate-300 mb-2" />
            <p className="text-sm text-slate-500">No active API key.</p>
            <p className="text-xs text-slate-400 mt-1">Generate a key to start integrating your tenant's API.</p>
          </div>
        ) : (
          <div className="rounded-xl border border-green-200 bg-white p-4 flex items-center gap-4" data-testid={`api-key-row-${activeKey.id}`}>
            <div className="h-2.5 w-2.5 rounded-full bg-green-500 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-slate-800">{activeKey.name || "API Key"}</p>
                <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-green-100 text-green-700">Active</span>
              </div>
              <p className="text-xs font-mono text-slate-400 mt-0.5">{activeKey.key_masked || "•••••••••••••••"}</p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Created {new Date(activeKey.created_at).toLocaleDateString()}
                {activeKey.last_used_at ? ` · Last used ${new Date(activeKey.last_used_at).toLocaleDateString()}` : " · Never used"}
              </p>
            </div>
            <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-600 shrink-0" onClick={() => handleRevoke(activeKey.id, activeKey.name)} data-testid={`revoke-key-${activeKey.id}`}>
              <Trash2 size={13} />
            </Button>
          </div>
        )}
      </div>

      {/* Quick start */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <p className="text-sm font-semibold text-slate-800">Quick Start</p>

        <div className="rounded-lg bg-blue-50 border border-blue-200 p-3 flex items-start gap-3">
          <Info size={14} className="text-blue-500 mt-0.5 shrink-0" />
          <p className="text-xs text-blue-700">
            <strong>No subdomain required.</strong> Your API key identifies your tenant on every request.
            Regardless of whether your customers access the platform via a subdomain or the main URL,
            all API calls use the same base URL — only the <code className="bg-blue-100 px-1 rounded font-mono">X-API-Key</code> header differs per tenant.
          </p>
        </div>

        <div className="space-y-3">
          <div>
            <p className="text-xs font-medium text-slate-600 mb-1">1. Every request must include your API key:</p>
            <pre className="bg-slate-900 text-green-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
{`X-API-Key: ak_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`}
            </pre>
          </div>
          <div>
            <p className="text-xs font-medium text-slate-600 mb-1">2. Example — fetch your products (cURL):</p>
            <pre className="bg-slate-900 text-blue-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
{`curl https://{base-url}/api/products \\
  -H "X-API-Key: ak_xxxxxxxx..."`}
            </pre>
          </div>
          <div>
            <p className="text-xs font-medium text-slate-600 mb-1">3. For customer-specific endpoints, also send a customer JWT:</p>
            <pre className="bg-slate-900 text-amber-300 text-[11px] font-mono p-3 rounded-lg overflow-x-auto">
{`# Step 1: Get the JWT
curl -X POST https://{base-url}/api/auth/customer-login \\
  -H "X-API-Key: ak_xxxxxxxx..." \\
  -H "Content-Type: application/json" \\
  -d '{"email":"customer@example.com","password":"..."}'

# Step 2: Use JWT + API Key together
curl https://{base-url}/api/subscriptions \\
  -H "X-API-Key: ak_xxxxxxxx..." \\
  -H "Authorization: Bearer eyJhbGci..."`}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Tab ──────────────────────────────────────────────────────────────────

export function ApiTab() {
  const [activeTag, setActiveTag] = useState<string>("All");
  const [searchTerm, setSearchTerm] = useState("");
  const [activeSection, setActiveSection] = useState<"keys" | "docs">("keys");
  const [testApiKey, setTestApiKey] = useState("");

  const filtered = API_ENDPOINTS.filter(ep => {
    const matchTag = activeTag === "All" || ep.tags.includes(activeTag);
    const matchSearch = !searchTerm || ep.path.toLowerCase().includes(searchTerm.toLowerCase()) || ep.summary.toLowerCase().includes(searchTerm.toLowerCase());
    return matchTag && matchSearch;
  });

  return (
    <div className="space-y-6" data-testid="api-tab">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">API</h2>
          <p className="text-sm text-slate-500 mt-0.5">Manage your API key and explore all available endpoints.</p>
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
            <BookOpen size={12} className="inline mr-1.5" />Documentation ({API_ENDPOINTS.length})
          </button>
        </div>
      </div>

      {activeSection === "keys" && (
        <ApiKeyManager onKeyResolved={key => { setTestApiKey(key); setActiveSection("docs"); }} />
      )}

      {activeSection === "docs" && (
        <div className="space-y-4">
          {/* Try It global API key input */}
          <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Key size={14} className="text-indigo-600" />
              <p className="text-xs font-semibold text-indigo-800">API Key for Try It</p>
            </div>
            <p className="text-xs text-indigo-600">Paste your API key here to enable live testing. Keys are never stored — paste fresh from your API Keys tab.</p>
            <div className="flex gap-2">
              <Input
                placeholder="ak_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                value={testApiKey}
                onChange={e => setTestApiKey(e.target.value)}
                className="font-mono text-xs h-8 bg-white border-indigo-200"
                data-testid="try-it-api-key-input"
              />
              {testApiKey && (
                <Button size="sm" variant="ghost" className="text-xs shrink-0" onClick={() => setTestApiKey("")}>Clear</Button>
              )}
            </div>
            {testApiKey && (
              <p className="text-[11px] text-indigo-600 flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500 inline-block" /> Key active for Try It on all endpoints below.
              </p>
            )}
          </div>

          {/* Auth model callout */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-indigo-200 bg-white p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700">X-API-Key</span>
                <span className="text-xs font-medium text-slate-700">Public endpoints</span>
              </div>
              <p className="text-[11px] text-slate-500">Required on every request. Identifies your tenant — no subdomain needed.</p>
            </div>
            <div className="rounded-lg border border-orange-200 bg-white p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-orange-100 text-orange-700">X-API-Key + JWT</span>
                <span className="text-xs font-medium text-slate-700">Customer endpoints</span>
              </div>
              <p className="text-[11px] text-slate-500">X-API-Key + customer Bearer JWT (from /api/auth/customer-login).</p>
            </div>
          </div>

          {/* Filter + search */}
          <div className="flex gap-5">
            {/* Tag filter */}
            <div className="w-44 shrink-0 space-y-1">
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 pb-1">Filter</p>
              {["All", ...ALL_TAGS].map(tag => (
                <button key={tag} onClick={() => setActiveTag(tag)}
                  className={`w-full text-left px-3 py-2 text-xs rounded-lg transition-colors ${activeTag === tag ? "bg-slate-900 text-white font-medium" : "text-slate-600 hover:bg-slate-100"}`}
                  data-testid={`api-tag-${tag.toLowerCase().replace(/\s+/g, "-").replace(/[&]/g, "")}`}
                >
                  {tag}
                </button>
              ))}
            </div>

            {/* Endpoints */}
            <div className="flex-1 min-w-0 space-y-2.5">
              <div className="flex items-center gap-3">
                <Input placeholder="Search endpoints…" value={searchTerm} onChange={e => setSearchTerm(e.target.value)} className="h-8 text-xs w-64" data-testid="api-search-input" />
                <span className="text-xs text-slate-400">{filtered.length} endpoint{filtered.length !== 1 ? "s" : ""}</span>
              </div>

              <div className="rounded-lg bg-slate-50 border border-slate-200 px-4 py-2.5 flex items-center gap-2">
                <Info size={13} className="text-slate-400 shrink-0" />
                <p className="text-[11px] text-slate-500">
                  All paths are relative — prepend your base URL: <code className="bg-white border px-1 rounded font-mono">https://your-domain.com</code>.
                  The <strong>X-API-Key</strong> resolves the tenant, so the same base URL works for all tenants.
                </p>
              </div>

              {filtered.map((ep, i) => (
                <EndpointCard key={i} ep={ep} testApiKey={testApiKey} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
